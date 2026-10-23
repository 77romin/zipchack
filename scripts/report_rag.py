"""저장된 실제 실행 기록으로 표·SVG·검토 보고서를 재생성한다."""
import json,csv,re,statistics
from pathlib import Path
from html import escape
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/검증/RAG_최종실험'

def svg(name,title,rows):
    width,height=940,110+len(rows)*48
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>{escape(title)}</title><rect width="100%" height="100%" fill="white"/><g font-family="Malgun Gothic, sans-serif" fill="#182532"><text x="28" y="38" font-size="22">{escape(title)}</text>']
    for i,(label,value,unit) in enumerate(rows):
        y=90+i*48
        parts.append(f'<text x="28" y="{y}" font-size="15">{escape(label)}</text><rect x="335" y="{y-19}" width="{min(460,value*4.6) if unit=="%" else min(460,value*75)}" height="25" rx="4" fill="#287b96"/><text x="810" y="{y}" font-size="15">{value:.1f}{unit}</text>')
    parts.append('</g></svg>');(OUT/name).write_text(''.join(parts),encoding='utf-8')

def main():
    data=json.loads((OUT/'raw.json').read_text(encoding='utf-8'))
    cases={c['id']:c for c in data['cases']};graded=[]
    for row in data['runs']:
        c=cases[row['case']];r=row.get('result',{});answer=r.get('answer','')
        # 정확성: 이 5문항의 원문과 답변을 검토한 보조 정량 규칙. 일반 사실성 평가기가 아니다.
        refusal=any(t in answer for t in ['확인할 수 없','알 수 없','확인해 드릴 수 없','제공할 수 없','답변을 유보','자료가 없어'])
        correct=all(t in answer for t in c['terms']) and not r.get('abstained',False) if c['answerable'] else refusal
        graded.append({'case':c['id'],'mode':row['mode'],'correct':int(bool(answer) and correct),'expected':c['expected'],
          'answerable':c['answerable'],'abstained':r.get('abstained'),'has_citation':bool(r.get('citations')),
          'wall_ms':row.get('wall_ms'),'answer':answer,'error':row.get('error','')})
    with (OUT/'graded.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(graded[0]));w.writeheader();w.writerows(graded)
    summary=[]
    for mode in ['no-rag','similarity','mmr']:
        rows=[r for r in graded if r['mode']==mode]
        positive=[r for r in rows if r['answerable']];negative=[r for r in rows if not r['answerable']]
        summary.append({'mode':mode,'correct':sum(r['correct'] for r in rows),'total':len(rows),
          'answerable_correct':sum(r['correct'] for r in positive),'answerable_total':len(positive),
          'refusal_correct':sum(r['correct'] for r in negative),'refusal_total':len(negative),
          'flag_correct':sum(r['abstained'] is True for r in negative),
          'cited_answerable':sum(r['has_citation'] for r in positive),
          'mean_seconds':statistics.mean(r['wall_ms'] for r in rows if r['wall_ms'])/1000})
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    retrieval_metrics=[]
    for mode in ['similarity','mmr']:
        rows=[r for r in data['runs'] if r['mode']==mode and 'retrieval' in r.get('result',{})]
        positive=[r for r in rows if cases[r['case']]['answerable']]
        supported=[]
        for row in positive:
            terms=cases[row['case']]['terms']
            chunks=[e for e in row['result']['retrieval']['evidence'] if e['metadata']['kind']=='external']
            matches=sum(all(term in e['text'] for term in terms) for e in chunks)
            supported.append({'case':row['case'],'matched':matches,'retrieved':len(chunks),'hit':matches>0})
        retrieval_metrics.append({'mode':mode,'positive_cases':supported,
          'hit_rate':sum(r['hit'] for r in supported)/len(supported),
          'strict_support_fraction':statistics.mean(r['matched']/r['retrieved'] if r['retrieved'] else 0 for r in supported),
          'mean_retrieve_ms':statistics.mean(r['result']['timings']['retrieve_ms'] for r in rows),
          'mean_generate_ms':statistics.mean(r['result']['timings']['generate_ms'] for r in rows)})
    (OUT/'retrieval_metrics.json').write_text(json.dumps(retrieval_metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    svg('quality.svg','固定5問 · 回答正確性（資料基準）'.replace('固定5問 · 回答正確性（資料基準）','고정 5문항 · 기준 자료에 따른 응답 판정'),[(r['mode'],r['correct']/r['total']*100,'%') for r in summary])
    svg('latency.svg','검색+생성 평균 시간 · 모드별 5회, 단일 실험',[(r['mode'],r['mean_seconds'],'초') for r in summary])
    top=data['top_k'];rows=[]
    for r in top:rows.append((r['mode']+' Top-k '+str(r['k']),r['external_count'],'개'))
    svg('top_k.svg','Top-k 변경 · 메타데이터 1개는 별도 포함',rows)
    md=['# RAG 전후·유사도/MMR 검증 결과','',data['method'],'',
      '## 판정 기준과 제한','',
      'Q1~Q3은 수집한 위키백과 판의 명시적 사실(청운동 지명 유래, 역삼동 분동일, 연남동 편입 유래), Q4~Q5는 자료가 없는 현재 매물·실시간 자전거 재고다. 원문과 실제 답변을 대조했다. CSV의 correct는 핵심 사실 일치 또는 미확인 답변 여부를 뜻하며, 응답 전체의 모든 문장을 전문가가 심사한 정확도가 아니다. no-RAG의 올바른 유보는 환각으로 분류하지 않는다. 정답 가능한 질문에서 답하지 못한 경우만 정답 미충족이다.',
      '', '모든 질문을 각 모드에서 1회 실행했다. 통계적 유의성·일반화·속도 우열을 결론내릴 수 없다. 같은 모델이지만 no-RAG에는 일반 지식을 허용하고 RAG에는 근거 한정·인용을 요구해 프롬프트가 다르다. 검색 알고리즘만의 인과 효과가 아니라 전체 답변 구성의 비교다. 모델 temperature/seed는 공급처 기본값이며 고정하지 않았다. 위키백과 내용을 역사적 절대 정답으로 단정하지 않고 해당 판 기준으로 평가한다.',
      '', '| 모드 | 기준 부합(5문항) | 답변 가능 정답(3) | 미확인 질문 유보(2) | 가능 질문 출처(3) | 유보 flag(2) | 평균 초 |', '|---|---:|---:|---:|---:|---:|---:|']
    for r in summary:md.append(f"| {r['mode']} | {r['correct']}/5 | {r['answerable_correct']}/3 | {r['refusal_correct']}/2 | {r['cited_answerable']}/3 | {r['flag_correct']}/2 | {r['mean_seconds']:.2f} |")
    md+=['','![](quality.svg)','','![](latency.svg)','','## Top-k 전후 근거','','| 모드 | 외부 Top-k | 실제 외부 청크 | 문서 제목(메타데이터 제외) |','|---|---:|---:|---|']
    for r in top:md.append(f"| {r['mode']} | {r['k']} | {r['external_count']} | "+' / '.join(e['metadata']['title'] for e in r['evidence'] if e['metadata']['kind']=='external')+' |')
    md+=['','![](top_k.svg)','','근거 수는 외부 청크 수다. 같은 문서의 여러 청크가 포함될 수 있고 화면의 사용된 인용 문서 수와 같지 않다. Top-k는 상한이며 자료가 부족하면 그보다 적다. 이번 공덕동 예시는 MMR에서 마포구 문서가 추가되었으나 그 사실만으로 더 정확하다고 결론내리지 않는다.',
      '', '## 원자료와 재현','',
      '- [질문·기준·실제 답변·검색 근거·시간](raw.json), [문항별 판정 CSV](graded.csv), [집계 JSON](summary.json).',
      '- `scripts/evaluate_rag.py`는 실제 GMS를 호출해 raw.json을 갱신한다. `scripts/report_rag.py`는 저장 기록만으로 보고서·SVG를 재생성한다.',
      '- 초기 실행에서 빈 답변·상태 문자열·비표준 인용 형식을 관찰했다. 초기 기록을 raw_initial.json에 보존하고, 유보 문구·인용 번호 정규화를 보완했다. 문장 내용과 유보 flag가 다를 수 있어 두 지표를 분리했다.',
      '- 수집·색인·UI 포함 시간은 이 표에 포함하지 않았다. collection_repeat.json은 별도의 첫/반복 준비 시간·HTTP 호출 수 기록이다.']
    md+=['','## 검색 단계의 별도 측정','','| 모드 | 답변 가능한 3질문 근거 적중률 | 핵심 사실 문자열 포함 청크율 평균 | 검색 평균 ms | 생성 평균 ms |','|---|---:|---:|---:|---:|']
    for r in retrieval_metrics:md.append(f"| {r['mode']} | {r['hit_rate']*100:.1f}% | {r['strict_support_fraction']*100:.1f}% | {r['mean_retrieve_ms']:.1f} | {r['mean_generate_ms']:.1f} |")
    md+=['','적중은 기준 핵심 사실 문자열이 모두 들어 있는 외부 청크가 하나 이상 검색되었는지로 판정했다. 청크율은 질문별 해당 청크 수/검색된 외부 청크 수의 평균이다. 이는 좁은 3문항의 문자열 지표이며 의미적 Precision/Recall 또는 전체 코퍼스의 관련성 정답 라벨을 대신하지 않는다. [원계산](retrieval_metrics.json).']
    (OUT/'결과보고서.md').write_text('\n'.join(md),encoding='utf-8')

if __name__=='__main__':main()
