"""지도 범위 이벤트 연결과 범위 내 법정동 자료 조회."""
import math,os,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import streamlit.components.v1 as components
from boundary_data import bundled_boundaries
from resident_api import fetch_residents

_map=components.declare_component('zipchack_viewport',path=str(Path(__file__).resolve().parent/'map_component'))

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
    value=_map(html=html,regions=regions,explore=explore,navigation=navigation,key='housing_viewport',default=None)
    if not value or not month:return
    try:
        bounds=validate_viewport(value)
    except ValueError:return
    codes=visible_codes(bounds,bundled_boundaries())
    st.caption(f'현재 지도 범위와 경계 사각영역이 겹치는 서울 법정동 {len(codes)}곳 · 자치구 구분 없이 조회합니다.')
    # 외접 사각형 교차로 조금 더 넓게 요청할 수 있지만, 보이는 동이 누락되지 않게 한다.
    if len(codes)>120:
        st.info('조회 범위가 넓습니다. 지도를 확대하면 최대 120개 동 범위에서 자동으로 자료를 불러옵니다.');return
    records=st.session_state.setdefault('resident_data',{})
    failures=st.session_state.setdefault('viewport_failures',{})
    now=time.time()
    missing=[c for c in codes if c+':'+month not in records and now-failures.get(c+':'+month,0)>60]
    if missing:
        key=os.getenv('MOIS_RESIDENT_API_KEY','')
        if not key.strip():st.warning('주민등록 API 키가 없어 지도 범위 자료를 불러올 수 없습니다.');return
        def fetch(code):
            try:return code,fetch_residents(code,month,key)
            except ValueError:return code,None
        with st.spinner(f'화면에 보이는 동네의 연령 자료 {len(missing)}곳을 불러옵니다...'):
            with ThreadPoolExecutor(max_workers=4) as pool:
                for code,data in pool.map(fetch,missing):
                    identity=code+':'+month
                    if data is None:failures[identity]=now
                    else:records[identity]=data;failures.pop(identity,None)
        st.rerun()
    failed=[c for c in codes if c+':'+month in failures]
    if failed:st.caption(f'{len(failed)}곳은 API 조회 미확인으로 회색입니다. 60초 후 지도 이동 시 재시도합니다.')
