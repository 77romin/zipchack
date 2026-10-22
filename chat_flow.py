"""조건 수집 대화의 단계와 응답. 추가 조건 질문은 한 번만 한다."""
import re
from chat_conditions import extract_patch, merge_conditions, next_question, DEFAULT_MODEL

def is_finish_request(message):
    text = re.sub(r'[\s,.!?。~]+', '', message)
    return bool(re.fullmatch(
        r'(?:없음|없어|없어요|없습니다|더없어|더없어요|추가조건없음)?'
        r'(?:알려줘|알려주세요|추천해줘|추천해주세요|추천해|찾아줘|진행해|진행해주세요)?', text)) and bool(text)

def summary(conditions):
    parts = [f"직장 {conditions['workplace']}", conditions['deal_type']]
    for key, label in [('deposit_max','보증금'), ('rent_max','월세'), ('purchase_max','매매가')]:
        if key in conditions:
            parts.append(f"{label} {conditions[key]:,}만원 이하")
    parts.append(f"{conditions['commute_mode']} 편도 {conditions['commute_minutes']}분 이내 희망")
    names = {'park':'공원', 'bike':'따릉이 대여소', 'subway':'지하철', 'parking':'주차장',
             'ev':'전기차 충전소', 'air':'대기환경', 'commerce':'상권', 'age':'희망 연령 구성'}
    selected = [names[key] for key,value in conditions.get('preferences', {}).items() if value > 0]
    if selected:
        parts.append('생활 선호: ' + '·'.join(selected))
    if conditions.get('preferred_ages'):
        parts.append('희망 주민 연령대: ' + '·'.join(f'{age}대' for age in conditions['preferred_ages']))
    return '\n'.join('- ' + part for part in parts)

def collect_turn(message, current, history, api_key, optional_asked=False, model=DEFAULT_MODEL):
    finished = is_finish_request(message)
    # '없음'은 추가 조건이 없다는 뜻이다. 저장한 조건을 지우는 모델 응답을 방지한다.
    patch = {} if finished else extract_patch(message, current, history, api_key, model)
    updated = merge_conditions(current, patch)
    question = next_question(updated)
    if question:
        prefix = '말씀하신 조건을 반영했어요. ' if patch else '추천 조건을 먼저 확인할게요. '
        return updated, prefix + question, optional_asked, 'collecting'
    has_optional = bool(updated.get('preferences') or updated.get('preferred_ages'))
    if not finished and not has_optional and not optional_asked:
        return updated, '기본 조건이 모였어요. 공원·따릉이·희망 주민 연령대 등 더 원하는 점이 있나요? 없으면 “없음, 추천해줘”라고 해주세요.', True, 'preferences'
    if not finished and not patch:
        return updated, '기존 조건은 유지했어요. 바꿀 조건을 구체적으로 알려주거나 “추천해줘”라고 해주세요.', True, 'ready'
    answer = ('추가 조건 없이 지금까지 정리한 조건으로 진행할게요.' if finished else '생활 선호를 포함해 조건을 정리했어요.')
    answer += '\n\n' + summary(updated)
    answer += ('\n\n조건 수집은 완료됐어요. 현재는 실거래가·동네 근거 검색이 미구현이라 '
               '이 조건에 맞는 실제 추천지를 아직 조회할 수 없어요. '
               '대중교통 통근시간도 아직 검증되지 않았어요. 조건을 유지하고 추천 데이터 연결 단계로 이어갈게요.')
    return updated, answer, True, 'waiting_for_data'
