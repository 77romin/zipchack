"""선택 법정동 지도 카드. 서로 다른 공간 단위의 통계를 섞지 않는다."""
import json,math
from age_colors import age_composition
from geo import stations_within
from rent_api import filter_budget

def read_boundaries(content):
    if len(content)>10*1024*1024:raise ValueError('경계 파일은 10MB 이하로 넣어주세요.')
    try:data=json.loads(content)
    except (ValueError,UnicodeError):raise ValueError('GeoJSON을 읽을 수 없습니다.') from None
    if data.get('type')!='FeatureCollection' or len(data.get('features',[]))>1000:
        raise ValueError('FeatureCollection 형식이 필요합니다.')
    result={}
    for feature in data['features']:
        properties=feature.get('properties') or {}
        code=str(properties.get('legal_code',''))
        if len(code)!=10 or not code.isdigit() or not code.startswith('11'):
            raise ValueError('각 영역의 properties.legal_code에 서울 법정동 10자리 코드가 필요합니다.')
        geometry=feature.get('geometry') or {}
        if geometry.get('type') not in {'Polygon','MultiPolygon'}:raise ValueError('Polygon 또는 MultiPolygon이 필요합니다.')
        polygons=geometry['coordinates'] if geometry['type']=='MultiPolygon' else [geometry['coordinates']]
        for polygon in polygons:
            if not polygon:raise ValueError('빈 경계입니다.')
            for ring in polygon:
                if len(ring)<4 or ring[0]!=ring[-1]:raise ValueError('경계 링은 닫혀 있어야 합니다.')
                for point in ring:
                    if len(point)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point) or not (126<=point[0]<=128 and 37<=point[1]<=38):
                        raise ValueError('서울 WGS84 경위도 순서의 좌표가 필요합니다.')
        if code in result:raise ValueError('중복 법정동 코드가 있습니다.')
        result[code]={'type':geometry['type'],'coordinates':geometry['coordinates']}
    return result

def map_card(neighborhood,result,conditions,bikes,residents,month):
    if not neighborhood:return None
    text=[]
    code=neighborhood.get('legal_code')
    same_district=bool(code and (result or {}).get('district_code')==code[:5])
    rows=filter_budget((result or {}).get('rows',[]) if same_district else [],conditions or {})
    rows=[r for r in rows or [] if r['dong']==neighborhood.get('dong')]
    text.append('과거 계약 자료 · 현재 호가·매물 아님')
    if rows:
        example=min(rows,key=lambda r:(r['monthly_rent'],r['deposit']))
        text.append(f"예산 내 거래 {len(rows)}건 · 예시 보증금 {example['deposit']:,} / 월세 {example['monthly_rent']:,}만원 ({example['contract_date']})")
    else:text.append('해당 조건의 거래 예시 미확인')
    if bikes:
        nearby=stations_within(bikes.get('stations',[]),neighborhood['latitude'],neighborhood['longitude'],.5)
        text.append(f'대표점 500m 안 따릉이 대여소 {len(nearby)}곳 · 직선거리·입력 자료 기준')
    else:text.append('따릉이 위치 자료 미확인 · 설정에서 공식 위치 파일을 불러오세요')
    code=neighborhood.get('legal_code');resident=residents.get(str(code)+':'+str(month))
    rates={}
    if resident and resident.get('total'):
        rates={str(age):round(value/resident['total']*100,1) for age,value in resident['ages'].items() if value is not None}
        text.append(f"주민등록 거주자 {resident['total']:,}명 · 기준월 {resident['month']} · 유동인구 아님")
    else:text.append('주민등록 연령 자료 미조회 · 생활환경 영역에서 조회할 수 있어요')
    return {'lines':text,'age_rates':rates,'month':month,'composition':age_composition(rates)}
