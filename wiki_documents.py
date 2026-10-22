"""명시적으로 매핑한 동네 자체 문서 수집. P1/P2 후보 선별은 후속 단계."""
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
import json,time
import requests
from rag_index import Source

API='https://ko.wikipedia.org/w/api.php'
LICENSE='CC BY-SA 4.0'
TERMS='https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use'
# 공식 법정동 코드와 페이지를 직접 확인한 초기 연결 목록.
TITLES={'1111010100':'청운동','1114016200':'신당동 (서울)','1144010200':'공덕동',
        '1144012400':'연남동','1168010100':'역삼동'}

def parse_page(payload,item,title):
    if payload.get('error'):
        raise ValueError('위키백과 API가 요청을 처리하지 못했습니다.')
    pages=list(payload.get('query',{}).get('pages',{}).values())
    if len(pages)!=1:
        raise ValueError('위키백과 문서를 하나로 확인하지 못했습니다.')
    page=pages[0]
    if 'missing' in page or 'disambiguation' in page.get('pageprops',{}) or page.get('ns')!=0:
        raise ValueError('자체 문서가 없거나 동음이의 문서입니다.')
    text=page.get('extract','').strip()
    intro=text.split('\n\n',1)[0]
    # 짧은 자체 문서도 허용한다. 다른 도시의 동명 문서를 붙이지 않는다.
    if not all(token in intro for token in ['서울',item['district'],item['name']]):
        raise ValueError('문서의 서울·자치구·동네 이름이 항목과 일치하지 않습니다.')
    revision=page.get('revisions',[{}])[0]
    if not revision.get('revid') or not revision.get('timestamp'):
        raise ValueError('문서 판 번호·기준시각을 확인하지 못했습니다.')
    actual=page['title']
    attribution=f"한국어 위키백과 기여자, {actual}; https://ko.wikipedia.org/w/index.php?title={quote(actual,safe='')}&action=history"
    return Source(item['code'],'wikipedia:'+str(page['pageid']),actual,text,
                  'https://ko.wikipedia.org/w/index.php?oldid='+str(revision['revid']),revision['timestamp'],
                  'external',LICENSE,str(revision['revid']),attribution)

def collect(item,title,cache_dir,contact='',refresh=False):
    identity=sha256(json.dumps([item['code'],item['district'],item['name'],title,'full-extract-v1'],ensure_ascii=False).encode()).hexdigest()
    path=Path(cache_dir)/(identity+'.json')
    if path.exists() and not refresh:
        record=json.loads(path.read_text(encoding='utf-8'))
        source=Source(**record['source'])
        if record['source_sha256']!=sha256(json.dumps(record['source'],sort_keys=True,ensure_ascii=False).encode()).hexdigest() or source.item_id!=item['code']:
            raise ValueError('수집 캐시의 내용·연결 항목을 확인해주세요.')
        return source,True
    for attempt in range(3):
        try:
            response=requests.get(API,params={'action':'query','format':'json','prop':'extracts|info|revisions|pageprops',
                'explaintext':1,'redirects':1,'rvprop':'ids|timestamp','ppprop':'disambiguation','titles':title,'maxlag':5},
                headers={'User-Agent':'Zipchack/0.1 ('+(contact or 'local educational RAG project')+')'},timeout=(5,25))
            response.raise_for_status()
            payload=response.json()
            if payload.get('error',{}).get('code')=='maxlag':
                raise requests.RequestException()
            break
        except (requests.RequestException,ValueError):
            if attempt==2:
                raise ValueError('위키백과 연결 실패: 네트워크·API 사용 정책을 확인해주세요.') from None
            time.sleep(attempt+1)
    source=parse_page(payload,item,title)
    record={'source':asdict(source),'fetched_at':datetime.now(timezone(timedelta(hours=9))).isoformat()}
    record['source_sha256']=sha256(json.dumps(record['source'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)
    return source,False
