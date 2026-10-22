"""선택 동네·질문에서 P1/P2를 실행하고 외부 문서를 색인한다."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from neighborhood_data import load_neighborhoods
from rag_index import Index,GmsEmbeddings
from rag_prepare import prepare

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--item',required=True,help='10자리 법정동 코드')
    p.add_argument('--question',required=True)
    p.add_argument('--output',type=Path,default=ROOT/'storage/rag_prepare_report.json')
    args=p.parse_args()
    index=None
    try:
        rows,_=load_neighborhoods();item=next((r for r in rows if r['code']==args.item),None)
        if item is None:raise ValueError('법정동 코드가 없습니다.')
        c=dotenv_values(ROOT/'.env');model=c.get('RAG_EMBEDDING_MODEL') or 'text-embedding-3-small'
        index=Index(ROOT/'storage/rag',GmsEmbeddings(c.get('GMS_KEY'),model),model)
        result=prepare(item,args.question,c.get('GMS_KEY'),ROOT/'storage/preparation',index,c.get('WIKI_CONTACT',''))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except ValueError:
        print('문서 준비에 실패했습니다. 동네 자체 문서 지원 여부·API 설정·네트워크를 확인해주세요.');return 1
    finally:
        if index:index.close()

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
