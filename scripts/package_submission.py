"""요구사항6장의 로컬 제출 ZIP 구성. 비밀·런타임·DB 제외, 원본 과제 PDF는 지정 시만 포함."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--identity',required=True,help='예: 서울_11반_김강민')
    p.add_argument('--requirements-pdf',type=Path)
    p.add_argument('--output-dir',type=Path,default=ROOT/'outputs/submission')
    a=p.parse_args()
    if any(c in a.identity for c in '/\\:*?"<>|'):raise ValueError('파일명에 사용할 수 없는 문자')
    name='AI 코어프로젝트 2_[집.착]_'+a.identity
    out=a.output_dir;out.mkdir(parents=True,exist_ok=True)
    folder=out/name
    if folder.exists():raise ValueError('동일 제출 폴더가 있습니다. 별도 이름을 사용하세요.')
    files=set(subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0'))
    files.update(str(f.relative_to(ROOT)).replace('\\','/') for f in (ROOT/'docs/제출').glob('*.md'))
    files.add('scripts/package_submission.py')
    selected=[]
    for rel in sorted(files):
        if not rel:continue
        path=Path(rel)
        if path.parts[0] in {'storage','tmp','.git','.venv','ref','outputs'}:
            if rel not in {'outputs/checklist-20261023/집착_2회차_셀프점검.xlsx','outputs/checklist-20261023/집착_2회차_상호점검_마예은.xlsx'}:continue
        if path.name.startswith('.env') and path.name!='.env.example':continue
        if path.suffix in {'.pyc','.log'} or not (ROOT/path).is_file():continue
        selected.append(rel)
    secrets=[value.encode() for key,value in dotenv_values(ROOT/'.env').items()
             if value and ('KEY' in key or 'TOKEN' in key) and len(value)>10]
    for rel in selected:
        source=ROOT/rel;content=source.read_bytes()
        if any(secret in content for secret in secrets):raise ValueError('제출 대상에 설정된 비밀 문자열이 있습니다. 파일명·내용은 출력하지 않습니다.')
        target=folder/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    if a.requirements_pdf:
        shutil.copy2(a.requirements_pdf,folder/'docs/AI코어프로젝트_2회차_요구사항정의서.pdf')
    intro='''# 집.착 프로젝트 제출 안내

작성자: 서울11반 김강민 · 제출 준비일: 2026-10-23

요구사항 정의서6장(21~23쪽)의 여섯 산출물에 맞춰 구성했습니다.

| 산출물 | 읽을 파일 |
| --- | --- |
| 1. 요구사항 정의서 | docs/제출/01_최종_요구사항정의서.md |
| 2. RAG 설계 | docs/RAG_파이프라인_설계.md, docs/제출/03_설계_제출보충.md, docs/RAG_파이프라인.puml·svg |
| 3. 검증 결과 | docs/제출/02_검증결과표.md, docs/검증/RAG_최종실험/ |
| 4. 소스 | app.py·각 모듈·scripts/·tests/·requirements.txt·data/ |
| 5. 셀프 체크리스트 | outputs/checklist-20261023/집착_2회차_셀프점검.xlsx |
| 6. README | README.md: 개요·기능·실행·데이터·실험·화면 |

사용자가 마예은의 상호 점검 결과가 셀프와 동일했다고 확인하여 별도 상호 점검 전사본을 포함했습니다. 구체적 피드백 원문은 제공되지 않아 임의로 작성하지 않았습니다. 기존 미확인3항목은 유지합니다. 자체 위키 문서 연결은5동네, 사용자 대기시간 수용성 등 한계를 공개한 제출본입니다.

.env·API키·가상환경·Git이력·로컬 Chroma DB·위키 요청 캐시·개발 임시파일은 제외했습니다. 기본 스냅샷은 포함하므로 `.env.example`을 복사해 본인 키를 입력하고 README의 설치·색인 명령을 실행합니다. 기존 DB를 배포하지 않아 최초 색인은 재실행해야 합니다. API 승인은 서비스별 필요합니다.

먼저 README.md를 읽고 다음으로 docs/제출/ 문서를 확인하세요. 실험 원자료는 당시 실행 기록이며 패키지 구성 작업에서 모델을 재호출한 결과가 아닙니다. 원본 과제 PDF에는 대외비 표시가 있으므로 허용된 교육 제출 범위에서 취급합니다. 이 패키지 생성은 lab.ssafy.com 업로드를 실행하지 않습니다.
'''
    (folder/'제출안내.md').write_text(intro,encoding='utf-8')
    entries=[]
    for file in sorted(folder.rglob('*')):
        if file.is_file():entries.append({'path':file.relative_to(folder).as_posix(),'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    (folder/'submission_manifest.json').write_text(json.dumps({'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'note':'작업 중 제출 문서와 사용자 추가 양식 포함. 원본 과제 PDF는 로컬 제출용 복사. 상호 점검: 마예은, 사용자 전달에 따라 동일 판정 전사본 포함.',
        'file_count_without_manifest':len(entries),'files':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    archive=out/(name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in folder.rglob('*'):
            if file.is_file():z.write(file,file.relative_to(out))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any(Path(n).name=='.env' for n in z.namelist())
        assert any(n.endswith('app.py') for n in z.namelist())
        assert any(n.endswith('집착_2회차_셀프점검.xlsx') for n in z.namelist())
    print(json.dumps({'zip':str(archive),'files':len(entries)+1,'bytes':archive.stat().st_size,
        'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},ensure_ascii=True))

if __name__=='__main__':main()
