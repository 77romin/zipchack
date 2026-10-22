"""색인된 자료로 LangGraph RAG 답변을 실행한다."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from rag_index import Index,GmsEmbeddings
from rag_pipeline import build_graph,run

def main():
    p=argparse.ArgumentParser(description='색인된 동네 근거로 LangGraph 답변 실행')
    p.add_argument('--item',required=True);p.add_argument('--question',required=True)
    p.add_argument('--mode',choices=['similarity','mmr'],default='similarity')
    p.add_argument('--output',type=Path,default=ROOT/'storage/rag_answer.json')
    a=p.parse_args();index=None
    try:
        c=dotenv_values(ROOT/'.env');model=c.get('RAG_EMBEDDING_MODEL') or 'text-embedding-3-small'
        index=Index(ROOT/'storage/rag',GmsEmbeddings(c.get('GMS_KEY'),model),model)
        result=run(build_graph(index,c.get('GMS_KEY')),a.item,a.question,mode=a.mode)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(result['answer']);print(json.dumps(result['citations'],ensure_ascii=False,indent=2));return 0
    except ValueError:
        print('RAG 답변 실패: 색인·키·네트워크·근거 인용 형식을 확인해주세요.');return 1
    finally:
        if index:index.close()

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
