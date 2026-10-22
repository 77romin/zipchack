"""공식 도시데이터의 반복 레코드를 행 단위로 읽는다. 서로 다른 시설의 필드를 섞지 않는다."""
import math
import xml.etree.ElementTree as ET

def text(node, tag):
    value=node.findtext(tag)
    return value.strip() if value and value.strip() else None

def number(node,tag, *, maximum=None, negative=False):
    try:
        value=float((text(node,tag) or "").replace(",",""))
        if not math.isfinite(value) or (not negative and value<0) or (maximum is not None and value>maximum):
            return None
        return value
    except (ValueError,TypeError):
        return None

def record_nodes(parent, section, identifier):
    return [node for node in parent.iter(section) if node.find(identifier) is not None]

def section_node(parent,section,identifiers):
    for node in parent.iter(section):
        if any(node.find(tag) is not None for tag in identifiers):
            return node
    return ET.Element("missing")

def parse_details(city):
    population=section_node(city,"LIVE_PPLTN_STTS",["AREA_PPLTN_MIN","MALE_PPLTN_RATE","FEMALE_PPLTN_RATE"])
    weather=section_node(city,"WEATHER_STTS",["TEMP","PM10","AIR_IDX"])
    commerce=section_node(city,"LIVE_CMRCL_STTS",["AREA_CMRCL_LVL","CMRCL_TIME","AREA_SH_PAYMENT_CNT"])
    parking=[]
    seen=set()
    for node in record_nodes(city,"PRK_STTS","PRK_NM"):
        identity=text(node,"PRK_CD") or (text(node,"PRK_NM"),text(node,"LAT"),text(node,"LNG"))
        if identity in seen: continue
        seen.add(identity)
        realtime=text(node,"CUR_PRK_YN")
        parking.append({"id":text(node,"PRK_CD"),"name":text(node,"PRK_NM"),
            "latitude":number(node,"LAT"),"longitude":number(node,"LNG"),
            "capacity":number(node,"CPCTY"),"realtime":realtime,
            "available":number(node,"CUR_PRK_CNT") if realtime=="Y" else None,
            "updated_at":text(node,"CUR_PRK_TIME"),"paid":text(node,"PAY_YN"),
            "base_fee":number(node,"RATES"),"base_minutes":number(node,"TIME_RATES"),
            "address":text(node,"ROAD_ADDR") or text(node,"ADDRESS")})
    subways=[]
    seen=set()
    for node in record_nodes(city,"SUB_STTS","SUB_STN_NM"):
        identity=(text(node,"SUB_STN_NM"),text(node,"SUB_STN_LINE"))
        if identity in seen: continue
        seen.add(identity)
        subways.append({"name":identity[0],"line":identity[1],
            "latitude":number(node,"SUB_STN_Y"),"longitude":number(node,"SUB_STN_X"),
            "address":text(node,"SUB_STN_RADDR") or text(node,"SUB_STN_JIBUN")})
    chargers=[]
    seen=set()
    for node in record_nodes(city,"CHARGER_STTS","STAT_NM"):
        identity=text(node,"STAT_ID") or (text(node,"STAT_NM"),text(node,"STAT_ADDR"))
        if identity in seen: continue
        seen.add(identity)
        details=[]
        # 충전기 목록의 컨테이너 이름과 무관하게 직접 CHARGER_ID를 가진 행만 읽는다.
        for row in node.iter():
            if row.find("CHARGER_ID") is not None:
                details.append({"id":text(row,"CHARGER_ID"),"type":text(row,"CHARGER_TYPE"),
                    "status_code":text(row,"CHARGER_STAT"),"updated_at":text(row,"STATUPDDT"),
                    "output_kw":number(row,"OUTPUT"),"method":text(row,"METHOD")})
        chargers.append({"id":text(node,"STAT_ID"),"name":text(node,"STAT_NM"),
            "latitude":number(node,"STAT_Y"),"longitude":number(node,"STAT_X"),
            "address":text(node,"STAT_ADDR"),"hours":text(node,"STAT_USETIME"),
            "restricted":text(node,"STAT_LIMITYN"),"restriction":text(node,"STAT_LIMITDETAIL"),
            "parking_fee":text(node,"STAT_PARKPAY"),"chargers":details})
    industries=[]
    for row in commerce.iter():
        if row.find("RSB_LRG_CTGR") is not None or row.find("RSB_MID_CTGR") is not None:
            industries.append({"category":text(row,"RSB_LRG_CTGR"),"subcategory":text(row,"RSB_MID_CTGR"),
                "level":text(row,"RSB_PAYMENT_LVL"),"payment_count":number(row,"RSB_SH_PAYMENT_CNT"),
                "amount_min":number(row,"RSB_SH_PAYMENT_AMT_MIN"),"amount_max":number(row,"RSB_SH_PAYMENT_AMT_MAX"),
                "merchant_count":number(row,"RSB_MCT_CNT"),"merchant_time":text(row,"RSB_MCT_TIME")})
    return {"gender_rates":{"남성":number(population,"MALE_PPLTN_RATE",maximum=100),
                            "여성":number(population,"FEMALE_PPLTN_RATE",maximum=100)},
        "parking":parking,"subways":subways,"ev_stations":chargers,
        "facility_sections":{"parking":city.find("PRK_STTS") is not None,
            "subways":city.find("SUB_STTS") is not None,"ev_stations":city.find("CHARGER_STTS") is not None},
        "subway_count":number(city,"SUB_STN_CNT"),"subway_time":text(city,"SUB_STN_TIME"),
        "temperature":number(weather,"TEMP",negative=True),
        "pm10":number(weather,"PM10"),"pm25":number(weather,"PM25"),"weather_time":text(weather,"WEATHER_TIME"),
        "air":{"grade":text(weather,"AIR_IDX"),"value":number(weather,"AIR_IDX_MVL"),
            "main_pollutant":text(weather,"AIR_IDX_MAIN"),"message":text(weather,"AIR_MSG")},
        "commerce":{"level":text(commerce,"AREA_CMRCL_LVL"),"payment_count":number(commerce,"AREA_SH_PAYMENT_CNT"),
            "amount_min":number(commerce,"AREA_SH_PAYMENT_AMT_MIN"),"amount_max":number(commerce,"AREA_SH_PAYMENT_AMT_MAX"),
            "updated_at":text(commerce,"CMRCL_TIME"),"industries":industries,
            "gender_rates":{"남성":number(commerce,"CMRCL_MALE_RATE",maximum=100),"여성":number(commerce,"CMRCL_FEMALE_RATE",maximum=100)},
            "age_rates":{label:number(commerce,tag,maximum=100) for label,tag in [
                ("10대 이하","CMRCL_10_RATE"),("20대","CMRCL_20_RATE"),("30대","CMRCL_30_RATE"),
                ("40대","CMRCL_40_RATE"),("50대","CMRCL_50_RATE"),("60대 이상","CMRCL_60_RATE")]}}}
