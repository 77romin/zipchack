"""공식 동네 메타데이터·공원·위키 문서 색인. --dry-run은 임베딩 요청 없이 준비 결과만 확인."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
from rag_index import Source,Index,GmsEmbeddings,park_sources,chunks
from neighborhood_data import neighborhood_sources,wiki_sources

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--db',type=Path,default=ROOT/'storage'/'rag')
    parser.add_argument('--items',type=Path,help='동네 메타데이터 JSONL: Source 필드 사용, kind=metadata')
    parser.add_argument('--chunk-size',type=int,default=1000)
    parser.add_argument('--overlap',type=int,default=200)
    args=parser.parse_args()
    try:
        sources=list(park_sources())+list(neighborhood_sources())+list(wiki_sources())
        if args.items:
            items=[Source(**json.loads(line)) for line in args.items.read_text(encoding='utf-8').splitlines() if line.strip()]
            if any(item.kind!='metadata' for item in items):
                raise ValueError('items 파일은 metadata 유형이어야 합니다.')
            sources+=items
        identities=[(s.kind,s.item_id,s.document_id) for s in sources]
        if len(set(identities))!=len(identities):
            raise ValueError('입력 문서 식별자가 중복되었습니다.')
        prepared=[chunks(s,args.chunk_size,args.overlap) for s in sources]
        report={'created_at':datetime.now(timezone.utc).isoformat(),'dry_run':args.dry_run,
            'documents':len(sources),'external_documents':sum(s.kind=='external' for s in sources),
            'metadata_items':len({s.item_id for s in sources if s.kind=='metadata'}),
            'prepared_chunks':sum(map(len,prepared)),'embedded':0,'removed':0,
            'chunk_size':args.chunk_size,'overlap':args.overlap}
        if not args.dry_run:
            config=dotenv_values(ROOT/'.env')
            model=config.get('RAG_EMBEDDING_MODEL') or 'text-embedding-3-small'
            index=Index(args.db,GmsEmbeddings(config.get('GMS_KEY'),model),model)
            try:
                results=index.put_many(sources,args.chunk_size,args.overlap)
                report['embedded']=sum(r['embedded'] for r in results)
                report['removed']=sum(r['removed'] for r in results)
                report['collection_counts']={k:c.count() for k,c in index.collections.items()}
            finally:
                index.close()
            report['model']=model
            args.db.mkdir(parents=True,exist_ok=True)
            (args.db/'last_index_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError) as error:
        # 원본 HTTP 응답·키·추적 정보 출력 금지
        print('색인 준비 또는 실행에 실패했습니다. 입력 파일·설정·API 접근을 확인해주세요.')
        return 1

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
