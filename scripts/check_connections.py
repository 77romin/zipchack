"""실제 연결 점검. 인증키·원본 응답·개인 대화를 출력/저장하지 않는다."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from pathlib import Path
import argparse,json,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from park_data import fetch_parks
from seoul_api import fetch_citydata
from resident_api import fetch_residents

def probe(name,key,call):
    if not key:
        return {'service':name,'status':'missing_key'}
    try:
        data=call(key)
        return {'service':name,'status':'success','count':len(data['parks']) if name=='parks' else data.get('total'),
                'observed_at':data.get('population_time') or data.get('month')}
    except ValueError as error:
        return {'service':name,'status':'failed','message':str(error)}

def check(config):
    month=(datetime.now(timezone(timedelta(hours=9))).replace(day=1)-timedelta(days=1)).strftime('%Y%m')
    tasks=[('parks',config.get('SEOUL_OPEN_DATA_API_KEY'),fetch_parks),
           ('citydata',config.get('SEOUL_OPEN_DATA_API_KEY'),lambda key:fetch_citydata('광화문·덕수궁',key)),
           ('residents',config.get('MOIS_RESIDENT_API_KEY'),lambda key:fetch_residents('1114016200',month,key))]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(probe,*task) for task in tasks]
        results=[future.result() for future in futures]
    return {'checked_at':datetime.now(timezone(timedelta(hours=9))).isoformat(),'results':results}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='인증키가 포함되지 않은 JSON 결과 저장 위치')
    args=parser.parse_args()
    report=check(dotenv_values(ROOT/'.env'))
    rendered=json.dumps(report,ensure_ascii=False,indent=2)
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered+'\n',encoding='utf-8')
    sys.exit(0 if all(row['status']=='success' for row in report['results']) else 1)
