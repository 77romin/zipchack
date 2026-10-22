"""카카오 지도 HTML 생성. 서버 REST 키는 전달하지 않는다."""
import json
import math
from urllib.parse import quote


def build_map_html(javascript_key, workplace=None, radius_km=3.0, stations=None, facilities=None):
    radius_km = float(radius_km)
    if not math.isfinite(radius_km) or not 0.5 <= radius_km <= 10:
        raise ValueError("탐색 반경은 0.5~10km여야 합니다.")
    center = {"latitude": 37.5665, "longitude": 126.9780}
    if workplace:
        lat, lon = float(workplace["latitude"]), float(workplace["longitude"])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("유효한 위도·경도가 필요합니다.")
        center = {"latitude": lat, "longitude": lon}
    payload = json.dumps({"center": center, "workplace": bool(workplace),
                          "stations": stations or [], "facilities": facilities or [], "radius_m": round(radius_km * 1000)}, ensure_ascii=False)
    # HTML의 script 종료 태그를 데이터로 삽입할 수 없게 한다.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.replace("__KEY__", quote(javascript_key, safe="")).replace("__DATA__", payload)


TEMPLATE = r'''
<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<style>html,body{margin:0;padding:0;font-family:sans-serif}#map{width:100%;height:500px;border-radius:12px}
#error{padding:12px;color:#b91c1c}#error:empty{display:none}</style></head><body>
<div id="error" role="alert"></div><div id="map" aria-label="직장과 탐색 범위 지도"></div>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KEY__&autoload=false"></script>
<script>
const data = __DATA__;
function fail(){document.getElementById('error').textContent='지도 연결을 확인해주세요. 카카오맵 활성화, JavaScript 키, SDK 등록 도메인을 확인하세요.';}
if(window.kakao && window.kakao.maps){
  kakao.maps.load(function(){
    const center = new kakao.maps.LatLng(data.center.latitude, data.center.longitude);
    const map = new kakao.maps.Map(document.getElementById('map'), {center:center, level:7});
    map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
    const stationInfo = new kakao.maps.InfoWindow({removable:true});
    (data.stations || []).forEach(function(station){
      const marker = new kakao.maps.Marker({map:map,
        position:new kakao.maps.LatLng(station.latitude,station.longitude),
        title:'따릉이 · '+station.name});
      kakao.maps.event.addListener(marker,'click',function(){
        const text = document.createElement('div');
        text.style.cssText='padding:12px;min-width:160px;max-width:260px;white-space:normal';
        text.textContent='따릉이 '+station.name+' · 직장에서 직선 '+station.distance_m+'m';
        stationInfo.setContent(text);
        stationInfo.open(map,marker);
      });
    });
    const facilityColors={parking:'#9333ea',subways:'#0284c7',ev_stations:'#16a34a'};
    const facilityBounds=new kakao.maps.LatLngBounds();
    (data.facilities || []).forEach(function(facility){
      const position=new kakao.maps.LatLng(facility.latitude,facility.longitude);
      facilityBounds.extend(position);
      const color=facilityColors[facility.kind] || '#64748b';
      const dot=new kakao.maps.Circle({map:map,center:position,radius:35,
        strokeColor:color,strokeWeight:2,fillColor:color,fillOpacity:0.85});
      kakao.maps.event.addListener(dot,'click',function(){
        const text=document.createElement('div');
        text.style.cssText='padding:12px;min-width:160px;max-width:280px;white-space:normal';
        text.textContent=facility.kind_name+' · '+facility.name+' · '+facility.detail;
        stationInfo.setContent(text);stationInfo.setPosition(position);stationInfo.open(map);
      });
    });
    if(!data.workplace && data.facilities.length){map.setBounds(facilityBounds);}
    if(data.workplace){
      new kakao.maps.Marker({map:map, position:center, title:'선택한 직장'});
      const circle = new kakao.maps.Circle({center:center, radius:data.radius_m,
        strokeWeight:2, strokeColor:'#2563EB', strokeOpacity:0.9,
        fillColor:'#60A5FA', fillOpacity:0.15});
      circle.setMap(map);
      map.setBounds(circle.getBounds());
    }
  });
}else{fail();}
</script></body></html>
'''
