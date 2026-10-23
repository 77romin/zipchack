"""선택 자치구의 법정동별 주민등록 스냅샷을 준비한다. 키는 저장하지 않는다."""
import sys,json,argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from neighborhood_data import load_neighborhoods
from resident_api import fetch_residents

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--district',default='11140');args=parser.parse_args()
    rows=[r for r in load_neighborhoods()[0] if r['code'].startswith(args.district)]
    if len(args.district)!=5 or not rows:raise ValueError('서울 자치구 5자리 코드를 확인해주세요.')
    month=(datetime.now(timezone(timedelta(hours=9))).replace(day=1)-timedelta(days=1)).strftime('%Y%m')
    output=ROOT/'storage'/('population_'+month+'.json');output.parent.mkdir(exist_ok=True)
    records=json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
    key=dotenv_values(ROOT/'.env').get('MOIS_RESIDENT_API_KEY','')
    missing=[r for r in rows if r['code'] not in records]
    def fetch(row):
        try:return row['code'],fetch_residents(row['code'],month,key)
        except ValueError:return row['code'],None
    failed=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for code,result in pool.map(fetch,missing):
            if result is None:failed.append(code)
            else:records[code]=result
    output.write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
    report={'month':month,'district':args.district,'requested':len(rows),'available':sum(r['code'] in records for r in rows),'failed':failed,'source_url':'https://www.data.go.kr/data/15108074/openapi.do'}
    (ROOT/'docs/검증'/('연령지도_구별조회_'+args.district+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(report)

if __name__=='__main__':main()
