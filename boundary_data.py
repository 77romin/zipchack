"""공개 법정동 경계와 공식 코드가 일치하는 폴리곤."""
from pathlib import Path
import json,hashlib
from map_explore import read_boundaries

ROOT=Path(__file__).resolve().parent

def bundled_boundaries():
    path=ROOT/'data/seoul_legal_boundaries.geojson'
    manifest=json.loads(path.with_suffix('.source.json').read_text(encoding='utf-8'))
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['normalized_sha256']:
        raise ValueError('경계 자료 해시가 다릅니다.')
    return read_boundaries(path.read_bytes())

def population_snapshot(month):
    path=ROOT/'storage'/('population_'+month+'.json')
    if not path.exists():return {}
    records=json.loads(path.read_text(encoding='utf-8'))
    return {code:{**data,'ages':{int(age):count for age,count in data['ages'].items()}} for code,data in records.items() if data.get('month')==month and data.get('code')==code}
