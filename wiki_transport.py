"""프로세스 안의 위키 HTTP 요청을 직렬화하고 연락처·호출 간격을 보장한다."""
from threading import RLock
import time
import requests

_LOCK=RLock()

def get(url,**kwargs):
    agent=kwargs.get('headers',{}).get('User-Agent','')
    if 'local educational RAG project' in agent or not agent:
        raise ValueError('WIKI_CONTACT에 이메일 또는 공개 연락처 URL을 설정해주세요.')
    with _LOCK:
        try:return requests.get(url,**kwargs)
        finally:time.sleep(.2)
