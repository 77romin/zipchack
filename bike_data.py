"""서울시 공식 대여소 CSV/XLSX에서 위치만 읽는다. 업로드 자료는 디스크에 저장하지 않는다."""
from io import BytesIO, StringIO
import math
import re
import pandas as pd

SOURCE_URL = "https://www.data.go.kr/data/15051893/fileData.do"

def normalize(value):
    return re.sub(r"[\s_()（）./-]", "", str(value)).lower().lstrip("\ufeff")

ALIASES = {
    "name": {"대여소명", "보관소대여소명", "대여소이름", "stationname", "name"},
    "latitude": {"위도", "latitude", "lat"},
    "longitude": {"경도", "longitude", "lon", "lng"},
    "id": {"대여소번호", "대여소id", "stationid", "id"},
}

def load_stations(content, filename, *, aliases=None):
    aliases = ALIASES if aliases is None else aliases
    if len(content) > 20 * 1024 * 1024:
        raise ValueError("20MB 이하의 대여소 위치 파일을 선택해주세요.")
    try:
        if filename.lower().endswith(".xlsx"):
            frame = pd.read_excel(BytesIO(content), header=None, dtype=str, engine="openpyxl").fillna("")
        elif filename.lower().endswith(".csv"):
            decoded = None
            for encoding in ("utf-8-sig", "cp949"):
                try:
                    decoded = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if decoded is None:
                raise ValueError("CSV 인코딩을 확인해주세요. UTF-8 또는 CP949를 지원합니다.")
            # 자료 상단의 제목·기준일 등은 헤더를 찾은 뒤 제외한다.
            import csv
            rows = list(csv.reader(StringIO(decoded)))
            frame = pd.DataFrame(rows).fillna("")
        else:
            raise ValueError("공식 위치 자료의 CSV 또는 XLSX 파일을 선택해주세요.")
    except ValueError:
        raise
    except Exception:
        raise ValueError("파일을 읽을 수 없습니다. CSV 또는 XLSX 형식을 확인해주세요.") from None

    columns, header_index = {}, None
    for index, row in frame.head(15).iterrows():
        candidate = {}
        for col, value in enumerate(row):
            for key, names in aliases.items():
                if normalize(value) in names:
                    candidate[key] = col
        # 공식 XLSX는 대여소명과 위도·경도가 서로 다른 병합 헤더 행에 있다.
        columns.update(candidate)
        if {"name", "latitude", "longitude"} <= columns.keys():
            header_index = index
            break
    if header_index is None:
        raise ValueError("대여소명·위도·경도 열을 찾지 못했습니다. 공식 대여소 위치 자료인지 확인해주세요.")

    stations, seen, skipped = [], set(), 0
    for _, row in frame.iloc[header_index+1:].iterrows():
        try:
            name = str(row.iloc[columns["name"]]).strip()
            lat = float(row.iloc[columns["latitude"]])
            lon = float(row.iloc[columns["longitude"]])
            if not name or not (math.isfinite(lat) and math.isfinite(lon) and 37 <= lat <= 38 and 126 <= lon <= 128):
                raise ValueError()
            station_id = str(row.iloc[columns["id"]]).strip() if "id" in columns else ""
            station_id = station_id or f"{lat:.6f}:{lon:.6f}"
            identity = (station_id, lat, lon)
            if identity in seen:
                skipped += 1
                continue
            seen.add(identity)
            stations.append({"id":station_id, "name":name, "latitude":lat, "longitude":lon})
        except (ValueError, TypeError, IndexError):
            skipped += 1
    if not stations:
        raise ValueError("서울 지역의 유효한 대여소 좌표가 없습니다.")
    return {"stations":stations, "skipped":skipped}


def bundled_stations():
    from pathlib import Path
    import json,hashlib
    path=Path(__file__).resolve().parent/'data/bikes_seoul.csv'
    manifest=json.loads(path.with_suffix('.source.json').read_text(encoding='utf-8'))
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['normalized_sha256']:
        raise ValueError('따릉이 위치 스냅샷 해시를 확인해주세요.')
    data=load_stations(path.read_bytes(),path.name)
    return {**data,'source_url':manifest['source_url'],'origin':'서울시 공식 위치 파일 · '+manifest['data_month'],
            'data_month':manifest['data_month'],'queried_at':manifest['downloaded_at'],'skipped':manifest['excluded_rows']}
