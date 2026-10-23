"""대화 후보의 위치·연령 준비와 지도/답변 공통 추천 모델."""
import os,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from housing_candidates import build_candidates
from housing_scores import compare_candidates,preference_weights,current_month
from neighborhood_api import resolve_neighborhood
from resident_api import fetch_residents


def prepare_candidates(result,conditions,context,failures=None,limit=20):
    context={**context,'points':dict(context.get('points',{})),'residents':dict(context.get('residents',{}))}
    failures=failures if failures is not None else {}
    month=context.get('month') or current_month();context['month']=month
    groups=build_candidates(result,conditions)['groups'][:limit]
    district=result['district_code'];now=time.time()
    wants_age=preference_weights(conditions).get('age',0)>0
    def fetch(group):
        identity=district+':'+group['dong'];point=context['points'].get(identity)
        if not point:
            if now-failures.get('point:'+identity,0)<60:return identity,None,None,[]
            try:point=resolve_neighborhood(district,group['dong'],os.getenv('KAKAO_REST_API_KEY',''))
            except ValueError:return identity,None,None,['point:'+identity]
        code=point.get('legal_code');resident=None;failed=[]
        if wants_age and code and str(code).startswith(district) and code+':'+month not in context['residents']:
            if now-failures.get('age:'+code+':'+month,0)>=60:
                try:resident=fetch_residents(code,month,os.getenv('MOIS_RESIDENT_API_KEY',''))
                except ValueError:failed.append('age:'+code+':'+month)
        return identity,point,resident,failed
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch,g) for g in groups]):
            identity,point,resident,failed=future.result()
            if point:context['points'][identity]=point;failures.pop('point:'+identity,None)
            if resident:
                context['residents'][resident['code']+':'+month]=resident
                failures.pop('age:'+resident['code']+':'+month,None)
            for key in failed:failures[key]=time.time()
    return context


def recommendation_rows(result,conditions,context):
    if not result:return []
    rows=compare_candidates(result,conditions or {},context)
    groups={g['dong']:g for g in build_candidates(result,conditions or {})['groups']}
    # 제외 기록이 있는 자료는 엄격한 순위를 유지하고 별도의 참고 순위만 제공한다.
    eligible=[r for r in rows if not r['missing'] and r['score'] is not None and not any('실거래' in issue for issue in r['issues'])]
    scores=sorted({r['score'] for r in eligible},reverse=True)
    ranks={score:1+sum(r['score']>score for r in eligible) for score in scores}
    provisional=any(row['issues'] for row in eligible)
    output=[]
    for row in rows:
        point=context.get('points',{}).get(result['district_code']+':'+row['dong'])
        reference=ranks.get(row['score']) if row in eligible else None
        label=('참고 '+str(reference) if reference is not None and provisional else str(row['rank']) if row['rank'] is not None else '후보')
        output.append({**row,'reference_rank':reference,'label':label,'provisional':provisional,'point':point,
                       'example':groups[row['dong']]['example']})
    output.sort(key=lambda row:(row['reference_rank'] is None,row['reference_rank'] or 0,row['dong']))
    return output


def recommendation_reply(result,conditions,context):
    rows=recommendation_rows(result,conditions,context)
    if not rows:return ''
    text='\n\n**지도와 함께 보는 생활 선호 비교·추천**'
    for row in rows[:5]:
        label=row['label']+'위' if row['label']!='후보' else '순위 미확정 후보'
        score=f"{row['score']:g}/100" if row['score'] is not None else '점수 미확인'
        text+=f"\n\n- **{row['dong']} · {label}** · {score} · 예산 내 과거 거래 {row['count']}건"
        for detail in row['details']:
            if detail['항목 점수'] is not None:text+='\n  - '+detail['항목']+': '+detail['근거']
        if row['missing'] or row['issues']:text+='\n  - 미확인/제한: '+', '.join(row['missing']+row['issues'])
        if not row['point']:text+='\n  - 대표 위치 미확인으로 지도 핀을 표시하지 못했어요.'
    text+='\n\n지도 번호와 위 순서는 같은 계산 결과를 사용해요. 참고 순위는 제외 기록이 있는 입력 자료 안의 비교이며 최종 추천 순위가 아니에요. 선호가 없거나 선택 항목이 미확인이면 번호 없이 후보로 표시해요. 현재 매물과 실제 통근시간은 확인한 결과가 아니에요.'
    return text
