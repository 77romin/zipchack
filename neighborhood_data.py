"""공식 법정동 목록: 행정동·생활권·시설 위치와 구분한다."""
import csv,hashlib,json,re,zipfile
from io import BytesIO,StringIO
from pathlib import Path
from rag_index import Source

ROOT=Path(__file__).resolve().parent
CODE_SOURCE='https://www.code.go.kr/stdcode/regCodeL.do'
DOWNLOAD_URL='https://www.code.go.kr/etc/codeFullDown.do'

def parse_codes(content):
    if len(content)>10*1024*1024:
        raise ValueError('법정동 파일 크기를 확인해주세요.')
    archive=zipfile.ZipFile(BytesIO(content))
    names=[n for n in archive.namelist() if n.endswith('.txt')]
    if len(names)!=1 or archive.getinfo(names[0]).file_size>20*1024*1024:
        raise ValueError('법정동 TXT 파일을 확인하지 못했습니다.')
    text=archive.read(names[0]).decode('cp949')
    reader=csv.DictReader(StringIO(text),delimiter='\t')
    if not {'법정동코드','법정동명','폐지여부'} <= set(reader.fieldnames or []):
        raise ValueError('법정동 파일의 필수 열이 없습니다.')
    rows={}
    for record in reader:
        code=(record.get('법정동코드') or '').strip()
        name=(record.get('법정동명') or '').strip()
        if (record.get('폐지여부') or '').strip()!='존재' or not code.startswith('11'):
            continue
        parts=name.split()
        if len(parts)!=3: # 시·자치구 집계 행 제외
            continue
        if not re.fullmatch(r'11\d{8}',code) or not code.endswith('00') or parts[0]!='서울특별시' or not parts[1].endswith('구'):
            raise ValueError('서울 법정동 코드·이름의 대응이 올바르지 않습니다.')
        if code in rows:
            raise ValueError('법정동 코드가 중복되었습니다.')
        rows[code]={'code':code,'name':parts[2],'district':parts[1],'full_name':name}
    return [rows[code] for code in sorted(rows)]

def load_neighborhoods():
    path=ROOT/'data'/'seoul_neighborhoods.csv'
    manifest=json.loads(path.with_suffix('.source.json').read_text(encoding='utf-8'))
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['normalized_sha256']:
        raise ValueError('법정동 스냅샷의 해시가 다릅니다.')
    rows=list(csv.DictReader(StringIO(path.read_text(encoding='utf-8'))))
    if len(rows)!=manifest['row_count'] or len({r['code'] for r in rows})!=len(rows):
        raise ValueError('법정동 스냅샷의 개수·식별자를 확인해주세요.')
    return rows,manifest

def neighborhood_sources():
    rows,manifest=load_neighborhoods()
    for row in rows:
        yield Source(row['code'],'legal-dong',row['full_name'],
            f"동네명: {row['name']}\n전체 이름: {row['full_name']}\n법정동 코드: {row['code']}\n자치구: {row['district']}\n단위: 법정동\n공식 코드 목록 상태: 존재\n이 목록은 행정동 경계·인구·가격·통근시간·주거 적합도를 제공하지 않습니다.",
            CODE_SOURCE,manifest['downloaded_at'],'metadata')

def wiki_sources():
    path=ROOT/'data'/'neighborhood_wiki.jsonl'
    if not path.exists():
        return
    manifest=json.loads(path.with_suffix('.source.json').read_text(encoding='utf-8'))
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['normalized_sha256']:
        raise ValueError('위키 문서 스냅샷의 해시가 다릅니다.')
    documents=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    codes={row['code'] for row in load_neighborhoods()[0]}
    if len(documents)!=manifest['row_count'] or any(d['item_id'] not in codes or d['kind']!='external' for d in documents):
        raise ValueError('위키 문서의 연결 항목을 확인해주세요.')
    for document in documents:
        yield Source(**document)
