"""지도 범위 이벤트 연결과 범위 내 법정동 자료 조회."""
import math,os,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import streamlit as st
import streamlit.components.v2 as components
from boundary_data import bundled_boundaries,save_population_snapshot
from resident_api import fetch_residents

FAILURE_LABELS={'connection':'연결 실패·시간 초과','http_error':'서버 HTTP 오류','api_rejected':'API 요청 거절(키·권한·기준월 확인)','no_data':'해당 법정동·기준월 자료 없음','invalid_response':'응답 형식·단일 집계·합계 검증 실패'}

_BRIDGE=(Path(__file__).resolve().parent/'map_component/bridge.js').read_text(encoding='utf-8')


def _viewport_component(**args):
    args.pop('default',None)
    key=args.pop('key')
    # 등록은 현재 실행 컨텍스트에서 수행한다(독립 AppTest 런타임도 지원).
    renderer=components.component('zipchack_viewport',js=_BRIDGE)
    result=renderer(data=args,key=key,default={'viewport':None},height=575,on_viewport_change=lambda:None)
    return result.viewport

def validate_viewport(value):
    if not isinstance(value,dict):raise ValueError('지도 범위 형식 오류')
    keys=['south','west','north','east']
    if any(type(value.get(k)) not in (int,float) or not math.isfinite(value[k]) for k in keys):raise ValueError('지도 범위 좌표 오류')
    if not (-90<=value['south']<value['north']<=90 and -180<=value['west']<value['east']<=180):raise ValueError('지도 범위 순서 오류')
    return {k:value[k] for k in keys}

def visible_codes(bounds,geometries):
    bounds=validate_viewport(bounds)
    codes=[]
    for code,g in geometries.items():
        polygons=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
        for polygon in polygons:
            xs=[p[0] for p in polygon[0]];ys=[p[1] for p in polygon[0]]
            if min(xs)<=bounds['east'] and max(xs)>=bounds['west'] and min(ys)<=bounds['north'] and max(ys)>=bounds['south']:
                codes.append(code);break
    return codes

def render_viewport(html,regions,explore,navigation,month):
    value=_viewport_component(html=html,regions=regions,explore=explore,navigation=navigation,status=st.session_state.get('viewport_status'),key='housing_viewport',default=None)
    if not value or not month:return
    try:
        bounds=validate_viewport(value)
    except ValueError:return
    codes=visible_codes(bounds,bundled_boundaries())
    st.caption(f'현재 지도 범위와 경계 사각영역이 겹치는 서울 법정동 {len(codes)}곳 · 자치구 구분 없이 조회합니다.')
    # 외접 사각형 교차로 조금 더 넓게 요청할 수 있지만, 보이는 동이 누락되지 않게 한다.
    if len(codes)>120:
        status={'bounds':bounds,'message':'범위가 넓습니다. 지도를 확대하면 연령 자료를 자동 조회합니다.'}
        if st.session_state.get('viewport_status')!=status:
            st.session_state.viewport_status=status;st.rerun()
        st.info('조회 범위가 넓습니다. 지도를 확대하면 최대 120개 동 범위에서 자동으로 자료를 불러옵니다.');return
    records=st.session_state.setdefault('resident_data',{})
    failures=st.session_state.setdefault('viewport_failures',{})
    reasons=st.session_state.setdefault('viewport_failure_reasons',{})
    retryable=[c for c in codes if c+':'+month not in records]
    if st.button('현재 화면 미확인 지역 다시 조회',key='retry_viewport',disabled=not retryable):
        for code in retryable:failures.pop(code+':'+month,None)
    now=time.time()
    missing=[c for c in codes if c+':'+month not in records and now-failures.get(c+':'+month,0)>60]
    if missing:
        key=os.getenv('MOIS_RESIDENT_API_KEY','')
        if not key.strip():
            status={'bounds':bounds,'message':'주민등록 API 키 미설정 · 연령 자료 조회를 시작할 수 없습니다.'}
            if st.session_state.get('viewport_status')!=status:
                st.session_state.viewport_status=status;st.rerun()
            st.warning('주민등록 API 키가 없어 지도 범위 자료를 불러올 수 없습니다.');return
        def fetch(code):
            try:return code,fetch_residents(code,month,key),None
            except ValueError as error:
                category=getattr(error,'category','invalid_response')
                return code,None,category if category in FAILURE_LABELS else 'invalid_response'
        progress=st.progress(0,text=f'연령 자료 조회 0/{len(missing)}곳 완료')
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(fetch,code) for code in missing]
            for count,future in enumerate(as_completed(futures),1):
                code,data,reason=future.result();identity=code+':'+month
                if data is None:
                    failures[identity]=time.time();reasons[identity]=reason
                else:
                    records[identity]=data;failures.pop(identity,None);reasons.pop(identity,None)
                progress.progress(count/len(missing),text=f'연령 자료 조회 {count}/{len(missing)}곳 완료')
        progress.empty()
        try:save_population_snapshot(month,records)
        except OSError:pass  # 세션 자료는 유지하며 캐시 저장 실패로 조회 결과를 버리지 않는다.
        st.rerun()
    failed=[c for c in codes if c+':'+month in failures]
    known=sum(c+':'+month in records for c in codes)
    status={'bounds':bounds,'message':f'현재 화면 조회 완료 · {known}/{len(codes)}곳 자료 확인 · {len(failed)}곳 미확인(회색)'}
    if st.session_state.get('viewport_status')!=status:
        st.session_state.viewport_status=status;st.rerun()
    if failed:
        st.caption(f'{len(failed)}곳은 미확인입니다. 위 버튼으로 즉시 재조회하거나 60초 후 지도 이동 시 재시도합니다.')
        with st.expander('미확인 지역과 원인 확인'):
            names={r['code']:r['name'] for r in regions}
            st.table([{'동네':names.get(code,code),'원인':FAILURE_LABELS.get(reasons.get(code+':'+month),'응답 검증 실패 또는 이전 조회 실패')} for code in failed])
    zero=[code for code in codes if records.get(code+':'+month,{}).get('total')==0]
    if zero:st.caption(f'{len(zero)}곳은 조회에 성공했지만 등록 인구가 0명이라 연령 비율을 계산하지 않습니다.')
