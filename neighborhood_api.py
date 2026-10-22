"""법정동 이름과 정확히 일치하는 카카오 지역 대표 좌표만 사용한다."""
import math
import re
from datetime import datetime,timezone,timedelta
import requests
from rent_api import DISTRICTS

SOURCE_URL='https://developers.kakao.com/docs/ko/local/dev-guide#address-coord'

class NeighborhoodError(ValueError):
    pass

def parse_neighborhood(payload,district,dong):
    matches=[]
    for item in payload.get('documents',[]):
        if not isinstance(item,dict) or item.get('address_type')!='REGION':
            continue  # 건물·도로·지번 검색 결과를 동네 대표점으로 대체하지 않는다.
        address=item.get('address') or {}
        parts=(item.get('address_name') or '').split()
        exact_name=len(parts)==3 and parts[0] in {'서울','서울특별시'} and parts[1:]==[district,dong]
        exact_fields=(address.get('region_1depth_name') in {'서울','서울특별시'}
                      and address.get('region_2depth_name')==district and address.get('region_3depth_name')==dong)
        if not (exact_name or exact_fields):
            continue
        try:
            lat,lon=float(item['y']),float(item['x'])
        except (ValueError,TypeError,KeyError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon) and 37<=lat<=38 and 126<=lon<=128):
            continue
        point={'latitude':lat,'longitude':lon,'name':f'{district} {dong}',
               'address':item['address_name'],'legal_code':address.get('b_code') if re.fullmatch(DISTRICTS[district]+r'\d{5}',address.get('b_code') or '') else None,'source_url':SOURCE_URL,
               'queried_at':datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')}
        if not any(p['latitude']==lat and p['longitude']==lon for p in matches):
            matches.append(point)
    if len(matches)!=1:
        raise NeighborhoodError('해당 구·법정동과 정확히 일치하는 지역 대표 위치를 하나로 확인하지 못했습니다. 다른 건물이나 인근 위치로 대체하지 않습니다.')
    return matches[0]

def resolve_neighborhood(district_code,dong,api_key):
    district=next((name for name,code in DISTRICTS.items() if code==district_code),None)
    if not district or not isinstance(dong,str) or not re.fullmatch(r'[가-힣0-9·.]{1,40}',dong):
        raise NeighborhoodError('조회한 서울 법정동을 선택해주세요.')
    if not api_key.strip():
        raise NeighborhoodError('.env에 KAKAO_REST_API_KEY를 설정해주세요.')
    try:
        response=requests.get('https://dapi.kakao.com/v2/local/search/address.json',
                              headers={'Authorization':'KakaoAK '+api_key.strip()},
                              params={'query':f'서울특별시 {district} {dong}','size':30},timeout=(5,10))
        response.raise_for_status()
        payload=response.json()
        if not isinstance(payload,dict) or not isinstance(payload.get('documents'),list):
            raise NeighborhoodError('카카오 지역 좌표 응답 형식을 확인하지 못했습니다.')
        point=parse_neighborhood(payload,district,dong)
        if not point.get('legal_code'):
            try:
                region=requests.get('https://dapi.kakao.com/v2/local/geo/coord2regioncode.json',
                                    headers={'Authorization':'KakaoAK '+api_key.strip()},
                                    params={'x':point['longitude'],'y':point['latitude']},timeout=(5,10))
                region.raise_for_status()
                matches=[item for item in region.json().get('documents',[]) if item.get('region_type')=='B'
                         and item.get('region_1depth_name') in {'서울','서울특별시'}
                         and item.get('region_2depth_name')==district and item.get('region_3depth_name')==dong
                         and re.fullmatch(district_code+r'\d{5}',item.get('code') or '')]
                if len(matches)==1:
                    point['legal_code']=matches[0]['code']
            except (requests.RequestException,ValueError,TypeError,AttributeError):
                point['legal_code']=None  # 좌표는 확인됐지만 법정동 코드는 미확인으로 유지한다.
        return point
    except requests.RequestException:
        raise NeighborhoodError('동네 위치를 조회하지 못했습니다. 카카오 REST 키·사용 권한·네트워크 상태를 확인해주세요.') from None
    except (ValueError,TypeError,KeyError) as error:
        if isinstance(error,NeighborhoodError):
            raise
        raise NeighborhoodError('카카오 지역 좌표 응답을 읽지 못했습니다.') from None
