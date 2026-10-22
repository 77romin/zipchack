"""공식 서울 법정동 목록과 검증된 초기 위키 문서를 준비한다."""
import argparse,csv,hashlib,json,sys,time,zipfile
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from io import StringIO
from pathlib import Path
import requests
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from neighborhood_data import CODE_SOURCE,DOWNLOAD_URL,parse_codes,load_neighborhoods
from wiki_documents import collect,TITLES,LICENSE,TERMS

def write(path,text):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes(text.encode('utf-8')); temporary.replace(path)

def prepare(refresh=False):
    folder=ROOT/'data'; folder.mkdir(exist_ok=True)
    file=folder/'seoul_neighborhoods.csv'
    if not file.exists() or refresh:
        try:
            response=requests.post(DOWNLOAD_URL,data={'codeseId':'법정동코드'},timeout=(5,30))
            response.raise_for_status()
            content=response.content
            rows=parse_codes(content)
        except (requests.RequestException,ValueError,zipfile.BadZipFile,UnicodeError):
            raise ValueError('공식 법정동 파일 다운로드·파싱에 실패했습니다.') from None
        if len(rows)<100 or len({r['district'] for r in rows})!=25:
            raise ValueError('서울 법정동 100건 이상·25개 자치구를 확인하지 못했습니다.')
        stream=StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=['code','name','district','full_name'])
        writer.writeheader(); writer.writerows(rows)
        text=stream.getvalue()
        manifest={'source_url':CODE_SOURCE,'download_url':DOWNLOAD_URL,'download_method':'POST codeseId=법정동코드',
            'downloaded_at':datetime.now(timezone(timedelta(hours=9))).isoformat(),'original_sha256':hashlib.sha256(content).hexdigest(),
            'normalized_sha256':hashlib.sha256(text.encode()).hexdigest(),'row_count':len(rows),'district_count':25,
            'selection':'법정동코드 11 시작, 폐지여부 존재, 서울특별시 자치구 법정동 3단계 이름',
            'scope':'법정동 식별 코드 목록. 가격·인구·경계 자료가 아님.',
            'attribution':'행정안전부 행정표준코드관리시스템',
            'usage_reference':'https://www.data.go.kr/data/15077871/openapi.do'}
        write(file,text); write(file.with_suffix('.source.json'),json.dumps(manifest,ensure_ascii=False,indent=2))
    rows,manifest=load_neighborhoods()
    by_code={r['code']:r for r in rows}
    documents=[]; failures=[]; cache_hits=0
    config=dotenv_values(ROOT/'.env')
    for code,title in TITLES.items():
        if code not in by_code:
            raise ValueError('초기 위키 연결 코드가 공식 목록에 없습니다.')
        hit=False
        try:
            source,hit=collect(by_code[code],title,ROOT/'storage'/'wiki',config.get('WIKI_CONTACT',''),refresh)
            documents.append(asdict(source)); cache_hits+=hit
        except ValueError as error:
            failures.append({'item_id':code,'title':title,'reason':str(error)})
        if not hit:
            time.sleep(0.2 if config.get('WIKI_CONTACT') else 6.1)
    # 실패한 재수집으로 기존 전체 스냅샷을 일부 덮어쓰지 않는다.
    if failures:
        print(json.dumps({'status':'failed','failures':failures},ensure_ascii=False))
        return 1
    text=''.join(json.dumps(d,ensure_ascii=False)+'\n' for d in documents)
    file=folder/'neighborhood_wiki.jsonl'
    manifest={'source_url':'https://ko.wikipedia.org/','license':LICENSE,'terms_url':TERMS,
        'downloaded_at':datetime.now(timezone(timedelta(hours=9))).isoformat(),'row_count':len(documents),
        'normalized_sha256':hashlib.sha256(text.encode()).hexdigest(),'transformation':'MediaWiki plaintext extract; full article, no minimum-length filtering',
        'scope':'검증된 초기 자체 문서 5건. 나머지 법정동 문서는 아직 수집하지 않음.',
        'attribution':'각 문서의 attribution·원문 판 링크 참조. 재배포 시 CC BY-SA 4.0 준수.'}
    write(file,text); write(file.with_suffix('.source.json'),json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({'neighborhoods':len(rows),'districts':len({r['district'] for r in rows}),
        'wiki_documents':len(documents),'cache_hits':cache_hits,'failures':0},ensure_ascii=False))
    return 0

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    try: sys.exit(prepare(args.refresh))
    except (ValueError,OSError):
        print('자료 준비 실패. 공식 파일·스냅샷·네트워크를 확인해주세요.'); sys.exit(1)
