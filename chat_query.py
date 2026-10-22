"""대화에서 수집한 명시적 조회 범위로 실거래 실행. 예산 변경은 캐시 재필터만 한다."""
import re
from chat_flow import collect_turn
from chat_conditions import next_question,DEFAULT_MODEL
from rent_api import DISTRICTS,fetch_rents,RentDataError
from housing_candidates import candidate_reply
from housing_scores import score_reply
from commute import commute_reply

QUERY_FIELDS={'district','deal_month','housing_types'}

def refresh_requested(message):
    return re.sub(r'[\s,.!?]+','',message) in {
        '다시조회해줘','다시조회해주세요','새로조회해줘','새로조회해주세요','재조회','최신자료로조회해줘'}

def query_question(conditions):
    for key,question in [
        ('district','어느 서울 자치구의 거래부터 살펴볼까요? 예: 중구. 통근시간만으로 조회 지역을 자동 결정하지는 않아요.'),
        ('deal_month','어느 계약월을 조회할까요? “지난달” 또는 “2026년 9월”처럼 알려주세요.'),
        ('housing_types','어떤 주택 유형을 조회할까요? 아파트·연립다세대·단독다가구·오피스텔 중 골라주세요. 모두 보려면 “주택 유형은 상관없어”라고 해주세요.')]:
        if key not in conditions:
            return question
    return None

def signature(conditions):
    return conditions['district']+':'+conditions['deal_month']+':'+','.join(sorted(conditions['housing_types']))

def same_query(result,conditions):
    return (result is not None and result.get('district_code')==DISTRICTS[conditions['district']]
            and result.get('month')==conditions['deal_month']
            and {status['category'] for status in result.get('statuses',[])}==set(conditions['housing_types']))

def run_chat_turn(message,current,history,api_key,keys,optional_asked=False,model=DEFAULT_MODEL,
                  rental_result=None,lifestyle_context=None,cache=None,commute_context=None):
    cache=dict(cache or {})
    refresh=refresh_requested(message)
    updated,answer,asked,stage=collect_turn('추천해줘' if refresh else message,current,history,api_key,
                                           optional_asked,model,rental_result=None)
    scope_changed=any(current.get(key)!=updated.get(key) for key in QUERY_FIELDS)
    output={'conditions':updated,'answer':answer,'asked':asked,'stage':stage,'result':None if scope_changed else rental_result,'cache':cache}
    if next_question(updated) or stage in {'preferences','ready'}:
        return output
    if updated.get('deal_type')=='매매':
        output.update(answer='매매 조건은 저장했어요. 현재 자동 실거래 조회는 전세·월세만 지원해요. 매매 가격 조회는 후속 단계예요.',stage='unsupported')
        return output
    # 기존 수동 조회 범위는 재사용하되, 범위를 하나라도 대화로 지정했다면 나머지까지 확인한다.
    legacy=rental_result is not None and not (QUERY_FIELDS & updated.keys()) and not refresh and not scope_changed
    question=query_question(updated)
    if question and not legacy:
        output.update(answer='주거 조건은 유지했어요. '+question,stage='query_conditions')
        # 명시적 범위 변경/삭제 중에는 이전 범위 자료를 새 조건의 결과로 제시하지 않는다.
        if QUERY_FIELDS & updated.keys():
            output['result']=None
        return output
    result=rental_result
    reused=legacy
    if not legacy:
        identity=signature(updated)
        if not refresh and same_query(rental_result,updated):
            result=rental_result; reused=True
        elif not refresh and identity in cache:
            result=cache[identity]; reused=True
        else:
            try:
                result=fetch_rents(DISTRICTS[updated['district']],updated['deal_month'],updated['housing_types'],keys)
                cache.pop(identity,None)
                cache[identity]=result
                while len(cache)>5:
                    cache.pop(next(iter(cache)))
            except RentDataError as error:
                output.update(answer='입력한 조건은 저장했어요. '+str(error),stage='query_failed',result=None)
                return output
        output['cache']=cache
    answer=('저장된 조회 자료에 현재 조건을 다시 적용했어요. ' if reused else '말씀하신 범위의 공식 전월세 거래를 조회했어요. ')
    answer+=candidate_reply(result,updated)
    if lifestyle_context is not None:
        answer+=score_reply(result,updated,lifestyle_context)
    if commute_context is not None:
        answer+=commute_reply(result,updated,commute_context)
    output.update(answer=answer,stage='candidates',result=result)
    return output
