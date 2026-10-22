"""실거래 근거로 동네 탐색 후보를 묶는다. 거래량을 적합도 점수로 쓰지 않는다."""
from collections import Counter
from rent_api import filter_budget, DISTRICTS

def build_candidates(result,conditions):
    statuses=result.get('statuses',[])
    successful=[status for status in statuses if not status.get('error')]
    partial=[status['category'] for status in statuses
             if status.get('error') or not status.get('complete') or status.get('skipped',0)>0]
    base={'district':next((name for name,code in DISTRICTS.items() if code==result.get('district_code')),'미확인'),
          'month':result.get('month','미확인'),'queried_at':result.get('queried_at','미확인'),
          'partial':partial,'groups':[],'matched':0,
          'categories':[status['category'] for status in successful]}
    if not successful:
        return {**base,'state':'failed'}
    rows=filter_budget(result.get('rows',[]),conditions)
    if rows is None:
        return {**base,'state':'missing_budget'}
    groups={}
    for row in rows:
        group=groups.setdefault(row['dong'],[])
        group.append(row)
    candidates=[]
    for dong,records in groups.items():
        counts=Counter(row['category'] for row in records)
        # 보증금 최저값과 월세 최저값을 서로 다른 계약에서 조합하지 않는다.
        example=min(records,key=lambda row:(row['monthly_rent'],row['deposit'],row['contract_date']))
        candidates.append({'dong':dong,'count':len(records),'categories':dict(counts),
                           'latest':max(row['contract_date'] for row in records),
                           'example':{key:example[key] for key in ['category','deposit','monthly_rent','contract_date','source_url']}})
    candidates.sort(key=lambda item:(-item['count'],item['dong']))
    return {**base,'state':'ok' if candidates else 'empty','matched':len(rows),'groups':candidates}

def candidate_reply(result,conditions):
    data=build_candidates(result,conditions)
    scope=f"서울 {data['district']} · 계약월 {data['month']} · 조회 {data['queried_at']}"
    if data['state']=='failed':
        return '실거래 조회가 모두 실패해서 후보를 만들지 못했어요. 거래가 없다는 뜻은 아니에요. 실거래 조회 화면의 오류를 확인해주세요.'
    if data['state']=='missing_budget':
        return '동네 후보를 추리려면 전월세 유형과 보증금·월세 상한을 먼저 확인해야 해요. 매매 후보는 아직 지원하지 않아요.'
    text='**조회한 거래에서 예산으로 추린 탐색 후보예요.**\n\n'+scope
    text+='\n조회 유형: '+', '.join(data['categories'])
    if data['partial']:
        text+='\n\n일부 조회 실패·상한·제외 기록이 있어 전체 결과가 아니에요: '+', '.join(data['partial'])
    if data['state']=='empty':
        return text+'\n\n이번 조회 범위에서 예산에 맞는 거래는 0건이에요. 예산은 그대로 유지했어요. 다른 구·계약월을 조회해볼 수 있으며 현재 매물이 없다는 뜻은 아니에요.'
    text+=f"\n\n예산에 맞는 거래 {data['matched']:,}건이 {len(data['groups'])}개 법정동에서 확인됐어요."
    for group in data['groups'][:5]:
        example=group['example']
        text+=(f"\n\n- **{group['dong']}**: {group['count']:,}건 · "
               f"거래 예시 보증금 {example['deposit']:,}만원 / 월세 {example['monthly_rent']:,}만원 "
               f"({example['category']}, {example['contract_date']}) "
               f"[공식 출처]({example['source_url']})")
    text+='\n\n예산에 맞는 조회 거래가 많은 동네 순으로 최대 5곳을 보여드렸어요. 종합 적합도 순위나 현재 매물이 아니에요.'
    text+=' 공원·따릉이 접근성·거주민 연령·실제 통근시간은 아직 확인하지 못했어요. 해당 희망사항은 유지하고 있어요.'
    return text
