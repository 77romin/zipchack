"""카카오맵 길찾기 연결과 사용자 확인 소요시간. 자동 경로시간 API가 아니다."""
import json
import math
import re
from datetime import datetime,timezone,timedelta
from urllib.parse import quote
import requests
from rent_api import DISTRICTS,filter_budget

MODES={'대중교통':'traffic','도보':'walk','자전거':'bicycle','자동차':'car'}
SOURCE_URL='https://apis.map.kakao.com/web/guide/#routeurl'

def coordinates(point):
    try:
        lat,lon=float(point['latitude']),float(point['longitude'])
    except (TypeError,KeyError,ValueError):
        raise ValueError('출발지와 직장 위치를 먼저 확인해주세요.') from None
    if not(math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
        raise ValueError('출발지와 직장의 좌표가 올바르지 않습니다.')
    return lat,lon

def route_url(origin,destination,mode):
    if mode not in MODES:
        raise ValueError('지원하는 통근수단을 선택해주세요.')
    def part(point):
        lat,lon=coordinates(point)
        return quote(point.get('name') or point.get('address') or '위치',safe='')+f',{lat:.7f},{lon:.7f}'
    return f'https://map.kakao.com/link/by/{MODES[mode]}/'+part(origin)+'/'+part(destination)

def record_key(origin,destination,mode,departure):
    if mode not in MODES:
        raise ValueError('지원하는 통근수단을 선택해주세요.')
    origin_coords=coordinates(origin); destination_coords=coordinates(destination)
    return json.dumps([origin.get('origin_kind','neighborhood'),*[round(n,7) for n in origin_coords],
                       *[round(n,7) for n in destination_coords],mode,departure],ensure_ascii=False)

def make_record(origin,destination,mode,departure,minutes,confirmed):
    if not confirmed:
        raise ValueError('카카오맵에서 같은 출발일시·수단의 총소요시간을 확인했는지 체크해주세요.')
    if type(minutes) is not int or not 1<=minutes<=1440:
        raise ValueError('확인한 편도 총소요시간을 1~1440분으로 입력해주세요.')
    try:
        datetime.strptime(departure,'%Y-%m-%d %H:%M')
    except (ValueError,TypeError):
        raise ValueError('경로를 확인한 출발일시를 입력해주세요.') from None
    return {'origin':dict(origin),'destination':dict(destination),'mode':mode,'departure':departure,
            'minutes':minutes,'method':'user_reported','route_url':route_url(origin,destination,mode),
            'recorded_at':datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')}

def assess_record(record,origin,destination,mode,departure,limit):
    if record is None:
        return {'state':'unknown','label':'미확인'}
    if record.get('method')!='user_reported' or record_key(record['origin'],record['destination'],record['mode'],record['departure'])!=record_key(origin,destination,mode,departure):
        return {'state':'unknown','label':'조건 불일치 · 미확인'}
    if type(limit) is not int or limit<1:
        return {'state':'unknown','label':'희망 통근시간 미입력'}
    minutes=record['minutes']
    return {'state':'within' if minutes<=limit else 'over','label':'희망시간 이내' if minutes<=limit else '희망시간 초과',
            'minutes':minutes,'difference':minutes-limit,'method':'사용자 확인값'}

def address_origin_candidates(result,conditions,dong):
    rows=filter_budget(result.get('rows',[]),conditions or {}) or []
    candidates={}
    for row in rows:
        if row['dong']!=dong or row['category']=='단독다가구' or not re.fullmatch(r'\d+(?:-\d+)?',row.get('jibun','')):
            continue
        district=next((name for name,code in DISTRICTS.items() if code==result['district_code']),None)
        if not district:
            continue
        address=f"서울특별시 {district} {dong} {row['jibun']}"
        candidates.setdefault(address,{'address':address,'district':district,'dong':dong,'jibun':row['jibun'],
                                       'name':row['name'] or address,'district_code':result['district_code']})
    return list(candidates.values())

def resolve_building(candidate,api_key):
    if not api_key.strip():
        raise ValueError('.env에 KAKAO_REST_API_KEY를 설정해주세요.')
    try:
        response=requests.get('https://dapi.kakao.com/v2/local/search/address.json',
                              headers={'Authorization':'KakaoAK '+api_key.strip()},
                              params={'query':candidate['address'],'analyze_type':'exact','size':30},timeout=(5,10))
        response.raise_for_status()
        matches=[]
        for document in response.json().get('documents',[]):
            address=document.get('address') or {}
            if (document.get('address_type')!='REGION_ADDR' or address.get('region_1depth_name') not in {'서울','서울특별시'}
                or address.get('region_2depth_name')!=candidate['district'] or address.get('region_3depth_name')!=candidate['dong']):
                continue
            actual=(address.get('main_address_no') or '')+('-'+address['sub_address_no'] if address.get('sub_address_no') else '')
            if actual!=candidate['jibun'] or address.get('mountain_yn')=='Y':
                continue
            point={'name':candidate['name'],'address':candidate['address'],'origin_kind':'building_address',
                   'latitude':document['y'],'longitude':document['x']}
            lat,lon=coordinates(point)
            point.update(latitude=lat,longitude=lon)
            if not any(coordinates(point)==coordinates(item) for item in matches):
                matches.append(point)
        if len(matches)!=1:
            raise ValueError('거래의 구·법정동·지번과 일치하는 주소 좌표를 하나로 확인하지 못했습니다. 동네 대표점으로 대체하지 않습니다.')
        return matches[0]
    except requests.RequestException:
        raise ValueError('주택 주소 위치를 확인하지 못했습니다. 카카오 REST 키·사용 권한·연결 상태를 확인해주세요.') from None
    except (KeyError,TypeError,AttributeError):
        raise ValueError('주택 주소 응답 형식을 확인하지 못했습니다.') from None

def commute_reply(result,conditions,context):
    destination=context.get('destination')
    if not destination or conditions.get('workplace')!=context.get('workplace_query'):
        return '\n\n**통근시간:** 현재 직장 위치를 검색 결과에서 선택해야 확인할 수 있어요.'
    mode=conditions.get('commute_mode'); limit=conditions.get('commute_minutes')
    departure=context.get('departure')
    if mode not in MODES or not departure:
        return '\n\n**통근시간:** 수단·출발일시가 미확인입니다.'
    from housing_candidates import build_candidates
    groups=build_candidates(result,conditions)['groups']
    text=f'\n\n**통근시간 확인 · {mode} · 출발 {departure} · 희망 {limit}분**'
    for group in groups[:5]:
        point=context.get('points',{}).get(result['district_code']+':'+group['dong'])
        if not point:
            text+=f"\n- {group['dong']}: 대표 위치 미확인"; continue
        record=context.get('records',{}).get(record_key(point,destination,mode,departure))
        assessed=assess_record(record,point,destination,mode,departure,limit)
        text+=f"\n- {group['dong']} 대표점: {assessed['label']}"
        if assessed['state']!='unknown':
            text+=f" · 사용자 확인 {assessed['minutes']}분 · 기록 {record['recorded_at']}"
    text+='\n\n카카오맵에서 확인해 직접 입력한 시간이며 자동 검증값이 아니에요. 대표점의 결과로 동네 전체 주택을 통과·탈락시키지 않아요. 주택 주소의 기록은 해당 주소에만 적용해요.'
    return text
