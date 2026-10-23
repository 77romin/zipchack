"""법정동 단일 단위(lv=7) 주민등록 거주자(regSeCd=2) 연령 통계."""
from datetime import datetime,timezone,timedelta
from urllib.parse import unquote
import re
import xml.etree.ElementTree as ET
import requests
from rent_api import number

SOURCE_URL='https://www.data.go.kr/data/15108074/openapi.do'

class ResidentLookupError(ValueError):
    def __init__(self,category,message):
        super().__init__(message)
        self.category=category


def parse_residents(content,code,month):
    if len(content)>2*1024*1024:
        raise ValueError('주민등록 응답 크기가 너무 큽니다.')
    try:
        root=ET.fromstring(content)
    except ET.ParseError:
        raise ValueError('주민등록 XML 응답을 읽지 못했습니다.') from None
    if root.findtext('.//head/resultCode') not in {'00','000','0','INFO-000'}:
        raise ResidentLookupError('api_rejected','주민등록 API가 요청을 처리하지 못했습니다. 이 API의 활용신청·키·조회월을 확인해주세요.')
    items=root.findall('.//item')
    if root.findtext('.//head/totalCount')=='0' and not items:
        raise ResidentLookupError('no_data','요청한 법정동·기준월의 자료가 없습니다.')
    if root.findtext('.//head/totalCount')!='1' or len(items)!=1:
        raise ValueError('법정동 단일 집계를 확인하지 못했습니다. 여러 행·통반 자료를 임의로 합산하지 않습니다.')
    item=items[0]
    values={child.tag.strip():(child.text or '').strip() for child in item}
    if values.get('stdgCd')!=code or values.get('statsYm')!=month:
        raise ValueError('주민등록 데이터의 법정동·기준월이 요청과 다릅니다.')
    ages={}
    for age in range(0,101,10):
        male=number(values.get(f'male{age}AgeNmprCnt'),True)
        female=number(values.get(f'feml{age}AgeNmprCnt'),True)
        ages[age]=male+female if male is not None and female is not None else None
    total=number(values.get('totNmprCnt'),True)
    if total is None or any(count is None for count in ages.values()) or sum(ages.values())!=total:
        raise ValueError('주민등록 총인구와 연령별 합계를 확인하지 못했습니다. 비율을 계산하지 않습니다.')
    return {'code':code,'month':month,'name':values.get('stdgNm') or '미제공','total':total,'ages':ages,
            'source_url':SOURCE_URL,'queried_at':datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')}

def fetch_residents(code,month,api_key):
    if not api_key.strip():
        raise ValueError('.env에 MOIS_RESIDENT_API_KEY를 설정해주세요. 법정동별 성/연령별 주민등록 인구수 API의 별도 활용신청이 필요합니다.')
    if not re.fullmatch(r'11\d{8}',code or ''):
        raise ValueError('정확한 서울 법정동 코드가 필요합니다. 동네 위치를 다시 조회해주세요.')
    try:
        parsed=datetime.strptime(month,'%Y%m')
        if len(month)!=6 or month<'202210' or month>=datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m'):
            raise ValueError()
    except ValueError:
        raise ValueError('주민등록 기준월은 202210부터 지난달까지 YYYYMM으로 입력해주세요.') from None
    try:
        response=requests.get('https://apis.data.go.kr/1741000/stdgSexdAgePpltn/selectStdgSexdAgePpltn',
                              params={'serviceKey':unquote(api_key.strip()),'stdgCd':code,'srchFrYm':month,
                                      'srchToYm':month,'lv':7,'regSeCd':2,'type':'XML','pageNo':1,'numOfRows':100},timeout=(5,20))
        response.raise_for_status()
    except requests.HTTPError:
        raise ResidentLookupError('http_error','주민등록 서버가 HTTP 오류를 반환했습니다.') from None
    except requests.RequestException:
        raise ResidentLookupError('connection','주민등록 API 연결에 실패했습니다. 키·사용 권한·네트워크 상태를 확인해주세요.') from None
    return parse_residents(response.content,code,month)

def preferred_share(data,ages):
    selected=sorted(set(ages))
    if not selected or not data['total'] or any(age not in data['ages'] for age in selected):
        return None
    return round(sum(data['ages'][age] for age in selected)/data['total']*100,1)
