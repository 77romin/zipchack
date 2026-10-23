"""연령 구성 비교 색상. 실제 평균 나이·평가 점수가 아니다."""
import math

def age_composition(rates):
    required=[20,30,60,70,80,90,100]
    values={age:rates.get(str(age),rates.get(age)) for age in required}
    if any(type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=100 for v in values.values()):return None
    young=values[20]+values[30]
    older=sum(values[age] for age in [60,70,80,90,100])
    if young+older<=0:return None
    score=older/(young+older)
    stops=[(22,163,74),(250,204,21),(220,38,38)]
    a,b=(stops[0],stops[1]) if score<=.5 else (stops[1],stops[2])
    weight=score*2 if score<=.5 else (score-.5)*2
    rgb=[round(x+(y-x)*weight) for x,y in zip(a,b)]
    return {'young_share':round(young,1),'older_share':round(older,1),'older_balance':round(score,4),
            'color':'#'+''.join(f'{x:02x}' for x in rgb)}
