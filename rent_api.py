"""국토교통부 공식 전월세 실거래 XML. 금액은 만원, 현재 매물이 아니다."""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import requests

SOURCES = {
    '아파트': ('Apt',15126474), '연립다세대': ('RH',15126473),
    '단독다가구': ('SH',15126472), '오피스텔': ('Offi',15126475),
}
DISTRICTS = dict(zip(
    ['종로구','중구','용산구','성동구','광진구','동대문구','중랑구','성북구','강북구','도봉구','노원구','은평구','서대문구','마포구','양천구','강서구','구로구','금천구','영등포구','동작구','관악구','서초구','강남구','송파구','강동구'],
    ['11110','11140','11170','11200','11215','11230','11260','11290','11305','11320','11350','11380','11410','11440','11470','11500','11530','11545','11560','11590','11620','11650','11680','11710','11740']))

class RentDataError(ValueError):
    pass

def field(node, name):
    return (node.findtext(name) or '').strip()

def number(value, integer=False):
    try:
        result=Decimal(value.replace(',','').strip())
        if not result.is_finite() or result < 0 or (integer and result != result.to_integral_value()):
            return None
        return int(result) if integer else float(result)
    except (InvalidOperation, ValueError, AttributeError):
        return None

def parse_page(content, category, district_code, month):
    if len(content)>10*1024*1024:
        raise RentDataError('실거래 응답 크기가 허용 범위를 초과했습니다.')
    try:
        document=ET.fromstring(content)
    except ET.ParseError:
        raise RentDataError('실거래 API의 XML 응답을 읽지 못했습니다.') from None
    code=document.findtext('./header/resultCode')
    if code not in {'000','00'}:
        # API가 돌려준 오류 원문에는 URL이나 키가 포함될 수 있어 출력하지 않는다.
        raise RentDataError('실거래 API가 요청을 처리하지 못했습니다. 해당 주택 유형의 활용신청·승인 상태와 인증키·호출 한도를 확인해주세요.')
    body=document.find('./body')
    if body is None:
        raise RentDataError('실거래 응답에 조회 결과가 없습니다.')
    total=number(field(body,'totalCount'), True)
    page=number(field(body,'pageNo'), True)
    if total is None or page is None or page<1:
        raise RentDataError('실거래 응답의 페이지 정보를 확인하지 못했습니다.')
    items=body.findall('./items/item')
    rows=[]
    skipped=0
    for item in items:
        deposit=number(field(item,'deposit'), True)
        rent=number(field(item,'monthlyRent'), True)
        dong=field(item,'umdNm')
        try:
            contract_date=date(int(field(item,'dealYear')),int(field(item,'dealMonth')),int(field(item,'dealDay')))
        except ValueError:
            contract_date=None
        sgg=field(item,'sggCd')
        if (deposit is None or rent is None or not dong or not contract_date
                or contract_date.strftime('%Y%m')!=month or sgg!=district_code):
            skipped+=1
            continue
        name=next((field(item,tag) for tag in ['aptNm','mhouseNm','offiNm'] if field(item,tag)), '')
        rows.append({'category':category,'district_code':district_code,'dong':dong,'name':name,
                     'deposit':deposit,'monthly_rent':rent,'deal_type':'전세' if rent==0 else '월세',
                     'area':number(field(item,'totalFloorAr' if category=='단독다가구' else 'excluUseAr')),
                     'area_type':'연면적' if category=='단독다가구' else '전용면적',
                     'contract_date':contract_date.isoformat(), 'contract_type':field(item,'contractType'),
                     'floor':field(item,'floor'), 'jibun':field(item,'jibun'),
                     'source_url':f'https://www.data.go.kr/data/{SOURCES[category][1]}/openapi.do'})
    return {'rows':rows,'total':total,'page':page,'received':len(items),'skipped':skipped}

def validate_query(district_code, month, categories):
    if district_code not in DISTRICTS.values():
        raise RentDataError('서울 시군구를 선택해주세요.')
    if not re.fullmatch(r'\d{6}',month):
        raise RentDataError('계약월을 YYYYMM 형식으로 입력해주세요. 예: 202609')
    try:
        value=datetime.strptime(month,'%Y%m').date()
    except ValueError:
        raise RentDataError('올바른 계약월을 입력해주세요.') from None
    today=datetime.now(timezone(timedelta(hours=9))).date()
    if value>today or value.year<2000:
        raise RentDataError('계약월은 2000년부터 현재 월 사이로 입력해주세요.')
    if not categories or any(category not in SOURCES for category in categories):
        raise RentDataError('조회할 주택 유형을 선택해주세요.')

def fetch_category(category, district_code, month, service_key, max_pages=5):
    suffix=SOURCES[category][0]
    url=f'https://apis.data.go.kr/1613000/RTMSDataSvc{suffix}Rent/getRTMSDataSvc{suffix}Rent'
    rows=[]
    received=skipped=0
    for page in range(1,max_pages+1):
        try:
            response=requests.get(url,params={'serviceKey':unquote(service_key.strip()),'LAWD_CD':district_code,
                                              'DEAL_YMD':month,'pageNo':page,'numOfRows':1000},timeout=(5,20))
            response.raise_for_status()
        except requests.RequestException:
            raise RentDataError('실거래 API 연결에 실패했습니다. 네트워크·서버 상태와 활용신청 상태를 확인해주세요.') from None
        result=parse_page(response.content,category,district_code,month)
        if result['page']!=page or (result['total']>received and result['received']==0):
            raise RentDataError('실거래 응답의 페이지가 일치하지 않아 조회를 중단했습니다.')
        rows+=result['rows']
        received+=result['received']
        skipped+=result['skipped']
        if received>=result['total']:
            return {'rows':rows,'total':result['total'],'received':received,'skipped':skipped,'complete':True}
    return {'rows':rows,'total':result['total'],'received':received,'skipped':skipped,'complete':False}

def fetch_rents(district_code,month,categories,service_key):
    validate_query(district_code,month,categories)
    if not service_key.strip():
        raise RentDataError('.env에 DATA_GO_KR_SERVICE_KEY를 입력하고 앱을 다시 실행해주세요. 선택한 주택 유형마다 공공데이터포털 활용신청이 필요합니다.')
    rows=[]
    statuses=[]
    for category in dict.fromkeys(categories):
        try:
            result=fetch_category(category,district_code,month,service_key)
            rows+=result.pop('rows')
            statuses.append({'category':category,**result,'error':None})
        except RentDataError as error:
            statuses.append({'category':category,'complete':False,'error':str(error)})
    return {'rows':rows,'statuses':statuses,'district_code':district_code,'month':month,
            'queried_at':datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')}

def filter_budget(rows, conditions):
    deal=conditions.get('deal_type','월세')
    if deal not in {'월세','전세'} or 'deposit_max' not in conditions or (deal=='월세' and 'rent_max' not in conditions):
        return None
    return [row for row in rows if row['deal_type']==deal and row['deposit']<=conditions['deposit_max']
            and (deal=='전세' or row['monthly_rent']<=conditions['rent_max'])]
