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

def map_card(neighborhood,result,conditions,bikes,residents,month,parks=None):
    if not neighborhood:return None
    text=[];sources=[]
    code=neighborhood.get('legal_code')
    same_district=bool(code and (result or {}).get('district_code')==code[:5])
    statuses=(result or {}).get('statuses',[])
    successful=any(not status.get('error') for status in statuses)
    filtered=filter_budget((result or {}).get('rows',[]) if same_district else [],conditions or {})
    rows=[r for r in filtered or [] if r['dong']==neighborhood.get('dong')]
    text.append('과거 계약 자료 · 현재 호가·매물 아님')
    if not same_district:text.append('이 동네의 전월세 거래 미조회')
    elif not successful:text.append('전월세 조회 성공 자료 미확인')
    elif filtered is None:text.append('예산 조건 미입력 · 전세/월세 유형과 예산을 대화로 알려주세요')
    else:
        text.append('거래 기준월 '+str(result.get('month','미확인'))+' · 조회 '+str(result.get('queried_at','미확인')))
        if rows:
            example=min(rows,key=lambda r:(r['monthly_rent'],r['deposit']))
            text.append(f"예산 내 과거 거래 {len(rows)}건 · 예시 보증금 {example['deposit']:,} / 월세 {example['monthly_rent']:,}만원 ({example['contract_date']})")
            for row in rows:
                url=row.get('source_url')
                if url and not any(source['url']==url for source in sources):sources.append({'title':'국토교통부 '+row.get('category','전월세')+' 실거래','url':url})
        else:text.append('이번 조회 범위에서 예산 내 과거 거래 0건 · 현재 매물이 없다는 뜻은 아님')
        if any(status.get('error') or not status.get('complete') or status.get('skipped',0) for status in statuses):
            text.append('일부 유형 실패·조회 상한·제외 기록이 있어 전체 거래가 아닐 수 있습니다')
    basis=neighborhood.get('point_basis','동네 대표점')
    text.append(basis+' 기준 500m 직선거리 · 개별 주택의 도보 접근성과 다릅니다')
    for dataset,key,label in [(bikes,'stations','따릉이 대여소'),(parks,'parks','주요 공원')]:
        if dataset is None:
            text.append(label+' 위치 자료 미확인');continue
        lat,lon=neighborhood['latitude'],neighborhood['longitude']
        # 500m를 포함하는 넉넉한 사각형으로 먼저 줄인 후 정확한 직선거리를 계산한다.
        candidates=[{**point,'id':point.get('id',point.get('name','')),'name':point.get('name','이름 미제공')} for point in dataset.get(key,[]) if abs(point['latitude']-lat)<.006 and abs(point['longitude']-lon)<.008]
        nearby=stations_within(candidates,lat,lon,.5)
        text.append(f'{label} {len(nearby)}곳'+(' · '+', '.join('{} {}m'.format(point['name'],point['distance_m']) for point in nearby[:3]) if nearby else ' · 입력 위치 자료 기준'))
        date=dataset.get('source_updated_at') or dataset.get('data_month') or dataset.get('queried_at') or '기준일은 원본 확인'
        text.append(label+' 자료: '+str(dataset.get('origin','입력 자료'))+' · '+str(date))
        if dataset.get('source_url'):sources.append({'title':label+' 공식 출처','url':dataset['source_url']})
    text.append('따릉이는 실시간 재고 아님 · 주요 공원 목록은 모든 공원의 전수자료가 아님')
    resident=residents.get(str(code)+':'+str(month));rates={}
    if resident and resident.get('total'):
        rates={str(age):round(value/resident['total']*100,1) for age,value in resident['ages'].items() if value is not None}
        text.append(f"주민등록 거주자 {resident['total']:,}명 · 기준월 {resident['month']} · 유동인구 아님")
        sources.append({'title':'주민등록 연령 통계','url':resident.get('source_url','https://www.data.go.kr/data/15108074/openapi.do')})
    elif resident and resident.get('total')==0:text.append('주민등록 인구 0명 · 연령 비율 계산 불가')
    else:text.append('주민등록 연령 자료 미조회·미확인 · 사이드바에서 조회 상태를 확인하세요')
    return {'lines':text,'sources':sources,'age_rates':rates,'month':month,'composition':age_composition(rates)}


def region_cards(regions,selected,result,conditions,bikes,parks,residents,month):
    cards=[]
    for region in regions:
        if (selected or {}).get('legal_code')==region['code']:
            point=selected
        else:
            point={**region,'legal_code':region['code'],'dong':region['name'].split()[-1],
                   'point_basis':'동 경계 기준점(대략)'}
        cards.append({**region,'card':map_card(point,result,conditions,bikes,residents,month,parks)})
    return cards
