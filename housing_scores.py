"""예산 후보의 생활 선호 비교. 계산 결과는 주거 종합 적합도나 통근 검증이 아니다."""
from datetime import datetime,timedelta,timezone
from geo import distance_m
from housing_candidates import build_candidates
from resident_api import preferred_share

LABELS={'park':'공원 접근성','bike':'따릉이 접근성','age':'희망 연령 구성',
        'subway':'지하철 접근성','parking':'주차장','ev':'전기차 충전','air':'대기환경','commerce':'상권'}

def selected_ages(conditions):
    if 'preferred_ages' in conditions:
        return conditions['preferred_ages']
    bounds=conditions.get('preferred_age_range')
    if bounds and len(bounds)==2 and bounds[0]%10==0 and bounds[1]%10==9:
        return list(range(bounds[0],min(bounds[1],99)+1,10))
    return []

def preference_weights(conditions):
    weights={key:value for key,value in conditions.get('preferences',{}).items() if value>0}
    if selected_ages(conditions) and 'age' not in conditions.get('preferences',{}):
        weights['age']=3  # 연령대 선호가 명시됐을 때의 공개된 기본 중요도
    return weights

def nearest_distance(point,records):
    if not records:
        return None
    return min(distance_m(point['latitude'],point['longitude'],record['latitude'],record['longitude']) for record in records)

def score_point(point,conditions,parks=None,bikes=None,resident=None):
    weights=preference_weights(conditions)
    known_weight=weighted_sum=0
    details=[]; missing=[]; issues=[]
    for feature,weight in weights.items():
        value=None; evidence='미확인'; source=''; reference='미확인'
        if feature in {'park','bike'}:
            data=parks if feature=='park' else bikes
            records=(data or {}).get('parks' if feature=='park' else 'stations')
            distance=nearest_distance(point,records)
            if distance is not None:
                value=max(0,1-distance/1500)*100
                evidence=f'대표점에서 자료 내 최근접 좌표까지 직선 {round(distance):,}m'
                source=data.get('source_url','원본 출처 확인 필요')
                reference=data.get('queried_at') or data.get('origin') or '원본 기준일 확인 필요'
                if data.get('skipped',0):
                    issues.append(LABELS[feature]+' 자료 제외 행 있음')
        elif feature=='age' and resident and point.get('legal_code')==resident.get('code'):
            value=preferred_share(resident,selected_ages(conditions))
            if value is not None:
                evidence='희망 주민등록 거주자 연령대 비율 '+f'{value:g}%'
                source=resident.get('source_url','원본 출처 확인 필요')
                reference=resident['month']
        if value is None:
            missing.append(LABELS.get(feature,feature))
        else:
            known_weight+=weight; weighted_sum+=value*weight
        details.append({'항목':LABELS.get(feature,feature),'중요도':weight,
                        '항목 점수':round(value,1) if value is not None else None,
                        '근거':evidence,'출처':source,'자료 시점/참조':reference})
    total_weight=sum(weights.values())
    return {'score':round(weighted_sum/known_weight,1) if known_weight else None,
            'coverage':round(known_weight/total_weight*100,1) if total_weight else 0,
            'complete':bool(total_weight) and not missing and not issues,
            'missing':missing,'issues':issues,'details':details}

def current_month():
    today=datetime.now(timezone(timedelta(hours=9)))
    return (today.replace(day=1)-timedelta(days=1)).strftime('%Y%m')

def compare_candidates(result,conditions,context):
    candidates=build_candidates(result,conditions)
    rows=[]
    month=context.get('month') or current_month()
    for group in candidates['groups']:
        identity=result['district_code']+':'+group['dong']
        point=context.get('points',{}).get(identity)
        if point:
            code=point.get('legal_code')
            resident=context.get('residents',{}).get(str(code)+':'+month)
            if resident and resident.get('month')!=month:
                resident=None
            score=score_point(point,conditions,context.get('parks'),context.get('bikes'),resident)
        else:
            weights=preference_weights(conditions)
            score={'score':None,'coverage':0,'complete':False,
                   'missing':['동네 대표 위치']+[LABELS.get(key,key) for key in weights],
                   'issues':[],'details':[]}
        if candidates['partial']:
            score['complete']=False
            score['issues'].append('실거래 일부 실패·상한·제외 기록 있음')
        rows.append({'dong':group['dong'],'count':group['count'],'month':month,**score})
    rows.sort(key=lambda row:(not row['complete'],row['score'] is None,-(row['score'] or 0),row['dong']))
    last_score=None; rank=0
    for index,row in enumerate([row for row in rows if row['complete']],1):
        if row['score']!=last_score:
            rank=index; last_score=row['score']
        row['rank']=rank
    for row in rows:
        row.setdefault('rank',None)
    return rows

def score_reply(result,conditions,context):
    if not preference_weights(conditions):
        return ''
    rows=compare_candidates(result,conditions,context)
    if not rows:
        return ''
    text='\n\n**생활 선호 비교 · 현재 확보한 자료 기준**'
    for row in rows[:5]:
        score=f"{row['score']:g}/100" if row['score'] is not None else '미확인'
        state=f"비교 {row['rank']}위" if row['rank'] is not None else '순위 미확정'
        text+=f"\n\n- {row['dong']}: {score} · 가중 근거 확인율 {row['coverage']:g}% · {state}"
        for detail in row['details']:
            if detail['항목 점수'] is not None:
                text+=f"\n  - {detail['항목']}: {detail['근거']} · 자료 {detail['자료 시점/참조']}"
                if detail['출처'].startswith('https://'):
                    text+=f" [출처]({detail['출처']})"
        if row['missing'] or row['issues']:
            text+='\n  - 미확인/제한: '+', '.join(row['missing']+row['issues'])
    if any(row['rank'] is None for row in rows):
        text+='\n\n미확정 후보가 있어 숫자로 표시된 순위도 확인된 후보끼리의 비교이며 전체 후보의 최종 순위는 아니에요.'
    text+='\n\n확인율은 선택한 선호 항목의 가중치 기준이며 자료의 완전성이나 추천 신뢰도 확률이 아니에요. 동네 대표점과 입력 자료 기준의 비교이며 실제 통근시간·개별 집의 적합도는 검증하지 않았어요.'
    return text
