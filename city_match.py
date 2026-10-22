"""사용자가 명시한 장소 환경 선호만 비교한다. 부동산 추천·거주민 통계·통근시간을 대신하지 않는다."""
import math
from geo import distance_m

FEATURE_LABELS={"parking":"주차장 수", "subway":"역·노선 수", "ev":"이용제한 없음 충전소 수",
                "air":"현재 대기환경", "commerce":"현재 상권 활동", "age":"현재 인구 연령대"}

def snapshot_key(data):
    return data.get("area_code") or data.get("area_name")

def upsert_snapshot(snapshots,data):
    key=snapshot_key(data)
    if not key: raise ValueError("장소 식별자가 없어 비교에 추가할 수 없습니다.")
    result=dict(snapshots)
    result[key]=data
    return result

def evaluate_place(data,preferences):
    weights=preferences.get("weights",{})
    factors={}
    park=data.get("parking",[])
    subway=data.get("subways",[])
    ev=data.get("ev_stations",[])
    factors['parking']=min(len(park)/5,1) if park else None
    factors['subway']=min(len(subway)/5,1) if subway else None
    known_ev=[r for r in ev if r.get('restricted') in ('Y','N')]
    factors['ev']=min(sum(r['restricted']=='N' for r in known_ev)/3,1) if known_ev and len(known_ev)==len(ev) else None
    air=data.get('air',{}).get('value')
    factors['air']=max(0,1-air/500) if air is not None else None
    count=data.get('commerce',{}).get('payment_count')
    if count is not None:
        activity=count/(count+1000)
        factors['commerce']=activity if preferences.get('commerce_direction','활발한 곳')=='활발한 곳' else 1-activity
    else: factors['commerce']=None
    ages=preferences.get('age_groups',[])
    rates=data.get('age_rates',{})
    values=[rates.get(age) for age in ages]
    factors['age']=min(sum(values)/100,1) if values and all(x is not None for x in values) else None
    selected={k:float(v) for k,v in weights.items() if k in FEATURE_LABELS and isinstance(v,(int,float)) and math.isfinite(v) and 0<v<=5}
    total=sum(selected.values())
    known=sum(weight for key,weight in selected.items() if factors[key] is not None)
    missing=[FEATURE_LABELS[key] for key in selected if factors[key] is None]
    score=round(100*sum(weight*factors[key] for key,weight in selected.items() if factors[key] is not None)/known,1) if known else None
    return {"score":score,"coverage":round(100*known/total,1) if total else None,
        "complete":bool(total) and known==total,"missing":missing,
        "details":[{"지표":FEATURE_LABELS[key],"중요도":weight,
            "지표 점수":round(factors[key]*100,1) if factors[key] is not None else None} for key,weight in selected.items()]}

def comparison_rows(snapshots,preferences):
    evaluated=[(data,evaluate_place(data,preferences)) for data in snapshots.values()]
    # 결측이 있는 장소에는 확정 순위를 주지 않는다.
    evaluated.sort(key=lambda pair:(not pair[1]['complete'], -(pair[1]['score'] or 0) if pair[1]['complete'] else 0, pair[0].get('area_name') or ''))
    rank=0; rows=[]
    for data,result in evaluated:
        if result['complete']: rank+=1
        rows.append({"순위":str(rank) if result['complete'] else '미확정',"장소":data.get('area_name') or data.get('area_code'),
            "현재환경 점수":result['score'],"가중 데이터 충족률(%)":result['coverage'],
            "미확인 지표":', '.join(result['missing']),"조회 시각":data.get('queried_at','미확인')})
    return rows

def facility_markers(data,kinds,workplace=None,radius_km=3):
    markers=[]
    for kind in kinds:
        for row in data.get(kind,[]):
            lat,lon=row.get('latitude'),row.get('longitude')
            if not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)): continue
            if not (math.isfinite(lat) and math.isfinite(lon) and 37<=lat<=38 and 126<=lon<=128): continue
            if workplace and distance_m(workplace['latitude'],workplace['longitude'],lat,lon)>radius_km*1000: continue
            kind_name={'parking':'주차장','subways':'지하철','ev_stations':'충전소'}[kind]
            detail=row.get('line') or row.get('address') or '주소 미제공'
            if kind=='ev_stations': detail+=' · '+(row.get('restriction') or '이용제한 확인 필요')
            markers.append({"kind":kind,"name":row.get('name') or kind_name,"kind_name":kind_name,
                "detail":detail,"latitude":lat,"longitude":lon})
    return markers
