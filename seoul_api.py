"""서울 도시데이터: XML 응답을 화면용 값으로 변환한다. 인증키/원본 오류는 표시하지 않는다."""
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import math
import xml.etree.ElementTree as ET
import requests
from city_schema import parse_details

SOURCE_URL = "https://data.seoul.go.kr/dataList/OA-21285/A/1/datasetView.do"

class SeoulDataError(ValueError):
    pass

def parse_citydata(content):
    if len(content)>10*1024*1024:
        raise SeoulDataError("도시데이터 응답이 너무 큽니다.")
    try:
        root=ET.fromstring(content)
    except ET.ParseError:
        raise SeoulDataError("서울시 응답 형식을 확인할 수 없습니다. 잠시 후 다시 조회해주세요.") from None
    code=root.findtext(".//RESULT/CODE") or root.findtext("./CODE")
    if code and code!="INFO-000":
        messages={"INFO-100":"서울 열린데이터 인증키를 확인해주세요.",
                  "INFO-200":"해당 장소의 데이터가 없습니다. 공식 장소명 또는 코드를 확인해주세요.",
                  "ERROR-300":"공식 장소명 또는 장소코드와 요청 설정을 확인해주세요.",
                  "ERROR-335":"샘플키의 요청 범위는 1~5입니다. 요청 설정을 확인해주세요."}
        raise SeoulDataError(messages.get(code,"도시데이터를 가져오지 못했습니다. 인증키·조회 한도·장소명을 확인해주세요."))
    city=root if root.tag=="CITYDATA" else root.find(".//CITYDATA")
    if city is None:
        raise SeoulDataError("장소별 도시데이터가 없습니다. 공식 장소명을 확인해주세요.")

    def text(tag):
        value=city.findtext(".//"+tag)
        return value.strip() if value and value.strip() else None
    def number(tag):
        value=text(tag)
        try:
            result=float(value.replace(",",""))
            return result if math.isfinite(result) and result>=0 else None
        except (ValueError,AttributeError):
            return None
    data = {"area_name":text("AREA_NM"),"area_code":text("AREA_CD"),
            "population_min":number("AREA_PPLTN_MIN"),"population_max":number("AREA_PPLTN_MAX"),
            "congestion":text("AREA_CONGEST_LVL"),"population_time":text("PPLTN_TIME"),
            "resident_rate":number("RESNT_PPLTN_RATE"),"nonresident_rate":number("NON_RESNT_PPLTN_RATE"),
            "replacement":text("REPLACE_YN"),
            "age_rates":{label:number(tag) for label,tag in [
                ("0~10세","PPLTN_RATE_0"),("10대","PPLTN_RATE_10"),("20대","PPLTN_RATE_20"),
                ("30대","PPLTN_RATE_30"),("40대","PPLTN_RATE_40"),("50대","PPLTN_RATE_50"),
                ("60대","PPLTN_RATE_60"),("70대 이상","PPLTN_RATE_70")]},
            "temperature":number("TEMP") if text("TEMP") is None else text("TEMP"),
            "pm10":number("PM10"),"pm25":number("PM25"),"weather_time":text("WEATHER_TIME"),
            "source_url":SOURCE_URL}
    data.update(parse_details(city))
    # 비율 필드는 결측·오류를 0이나 유효한 비율로 바꾸지 않는다.
    for label,value in data["age_rates"].items():
        if value is not None and value>100: data["age_rates"][label]=None
    return data

def fetch_citydata(area_name,api_key):
    area_name=area_name.strip()
    if not area_name or len(area_name)>100:
        raise SeoulDataError("공식 장소명 또는 장소코드를 입력해주세요.")
    if not api_key.strip():
        raise SeoulDataError(".env에 SEOUL_OPEN_DATA_API_KEY를 설정해주세요.")
    # 서울시 공식 예제의 서버 주소·형식을 사용한다. URL에 키가 포함되므로 예외 전문을 노출하지 않는다.
    url="http://openapi.seoul.go.kr:8088/"+quote(api_key.strip(),safe="")+"/xml/citydata/1/1/"+quote(area_name,safe="")
    try:
        response=requests.get(url,timeout=(5,20))
        response.raise_for_status()
    except requests.RequestException:
        raise SeoulDataError("서울시 연결에 실패했습니다. 네트워크와 API 서비스 상태를 확인해주세요.") from None
    data=parse_citydata(response.content)
    data["queried_at"]=datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S KST")
    return data
