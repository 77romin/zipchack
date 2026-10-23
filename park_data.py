"""서울시 주요 공원 좌표. 누락·범위 제한을 모두 공원이 없다는 뜻으로 해석하지 않는다."""
import math
from datetime import datetime,timezone,timedelta
from urllib.parse import quote
import requests
from bike_data import load_stations

SOURCE_URL='https://data.seoul.go.kr/dataList/OA-394/S/1/datasetView.do'
ALIASES={'name':{'공원명','공원이름','ppark','parkname','name'},
         'latitude':{'위도','latitude','lat','y좌표wgs84'},'longitude':{'경도','longitude','lon','lng','x좌표wgs84'},
         'id':{'공원번호','pidx','id','연번'}}

def load_parks(content,filename):
    try:
        result=load_stations(content,filename,aliases=ALIASES)
    except ValueError as error:
        raise ValueError(str(error).replace('대여소','공원')) from None
    return {'parks':result['stations'],'skipped':result['skipped'],'source_url':SOURCE_URL,'origin':filename,
            'queried_at':datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')}

def fetch_parks(api_key):
    if not api_key.strip():
        raise ValueError('.env에 SEOUL_OPEN_DATA_API_KEY를 설정해주세요.')
    url='http://openapi.seoul.go.kr:8088/'+quote(api_key.strip(),safe='')+'/json/SearchParkInfoService/1/1000/'
    try:
        response=requests.get(url,timeout=(5,20)); response.raise_for_status()
        data=response.json()
        if not isinstance(data,dict):
            raise ValueError('서울 공원 API 응답 형식을 확인하지 못했습니다.')
        section=data.get('SearchParkInfoService',{})
        if not isinstance(section,dict):
            raise ValueError('서울 공원 API 응답 형식을 확인하지 못했습니다.')
        if section.get('RESULT',{}).get('CODE')!='INFO-000':
            raise ValueError('서울 공원 API가 요청을 처리하지 못했습니다. 인증·조회 한도·서비스 상태를 확인해주세요.')
        rows=section['row']
        try:
            total=int(section['list_total_count'])
        except (ValueError,TypeError):
            raise ValueError('공원 API의 전체 건수를 확인하지 못했습니다.') from None
        if not isinstance(rows,list) or total!=len(rows):
            raise ValueError('공원 전체 목록을 받지 못했습니다. 파일 자료로 확인해주세요.')
        parks=[]; seen=set(); skipped=0
        for item in rows:
            try:
                if not isinstance(item,dict):
                    raise ValueError()
                name=str(item.get('P_PARK') or '').strip()
                lat,lon=float(item['LATITUDE']),float(item['LONGITUDE'])
                if not name or not(math.isfinite(lat) and math.isfinite(lon) and 37<=lat<=38 and 126<=lon<=128):
                    raise ValueError()
                identity=(name,lat,lon)
                if identity in seen:
                    skipped+=1; continue
                seen.add(identity)
                parks.append({'id':str(item.get('P_IDX') or name),'name':name,'latitude':lat,'longitude':lon})
            except (KeyError,ValueError,TypeError):
                skipped+=1
        if not parks:
            raise ValueError('유효한 공원 좌표가 없습니다. 공식 위치 파일을 확인해주세요.')
        return {'parks':parks,'skipped':skipped,'source_url':SOURCE_URL,'origin':'서울 주요 공원 API',
                'queried_at':datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')}
    except requests.RequestException:
        raise ValueError('서울 공원 API에 연결하지 못했습니다. 네트워크와 서버 상태를 확인하거나 좌표가 포함된 공식 CSV/XLSX를 사용해주세요.') from None
    except (KeyError,TypeError):
        raise ValueError('서울 공원 API 응답 형식을 확인하지 못했습니다.') from None


def bundled_parks():
    """실조회와 구별되는 공식 CSV 스냅샷. 원본 출처/해시/제외 건수 표시."""
    from pathlib import Path
    import json
    folder=Path(__file__).resolve().parent/'data'
    result=load_parks((folder/'parks_seoul.csv').read_bytes(),'parks_seoul.csv')
    manifest=json.loads((folder/'parks_seoul.source.json').read_text(encoding='utf-8'))
    result.update(origin='서울시 공식 CSV 스냅샷 · API 실조회 아님',
                  queried_at=manifest['downloaded_at'],source_updated_at=manifest['dataset_updated_at'],
                  skipped=manifest['excluded_rows'],source_url=manifest['source_url'],license=manifest['license'])
    return result
