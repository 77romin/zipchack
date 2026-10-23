"""추천 후보와 동일한 대표점의 공식 자료를 RAG 문서로 변환한다."""
import json
from rag_index import Source
from geo import stations_within


def candidate_sources(point, context):
    code=point['legal_code']
    name=point.get('dong') or point.get('name') or code
    for key,records,label in [('bikes','stations','따릉이 대여소'),('parks','parks','주요 공원')]:
        data=context.get(key) or {}
        date=data.get('source_updated_at') or data.get('data_month') or data.get('queried_at')
        if not data.get('source_url') or not date or records not in data:continue
        points=[{**row,'id':row.get('id',''),'name':row.get('name','이름 미제공')} for row in data[records]]
        nearby=stations_within(points,point['latitude'],point['longitude'],.5)
        body=f"{name}의 대표점 ({point['latitude']}, {point['longitude']}) 기준 500m 직선거리 내 {label} {len(nearby)}곳.\n"
        body+='\n'.join(f"{row['name']}: 직선 {row['distance_m']}m" for row in nearby)
        body+='\n개별 주택의 도보거리·통근시간이 아니다. 따릉이는 실시간 재고가 아니며 주요 공원 목록은 전체 공원 전수자료가 아니다.'
        yield Source(code,'candidate-'+key,label+' 위치 근거 · '+name,body,data['source_url'],str(date))
    month=context.get('month')
    resident=context.get('residents',{}).get(code+':'+str(month))
    if resident and resident.get('code')==code and resident.get('month')==month and resident.get('source_url'):
        body=f"{name} 주민등록 거주자 통계. 기준월 {month}. 유동인구·생활인구가 아니다.\n"
        body+=json.dumps({'total':resident['total'],'ages':resident['ages']},ensure_ascii=False)
        body+='\nages 키는 10세 구간의 시작 나이이며 100은 100세 이상이다. 인구 0명일 때 비율은 계산할 수 없다.'
        yield Source(code,'candidate-residents-'+month,'주민등록 연령 근거 · '+name,body,resident['source_url'],month)


def target_candidate(rows, fallback):
    """좌표와 법정동 코드가 확인된 최상위 후보를 선택한다."""
    return next((row['point'] for row in rows if (row.get('point') or {}).get('legal_code')),fallback)
