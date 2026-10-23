"""카카오 지도 HTML 생성. 서버 REST 키는 전달하지 않는다."""
import json
import math
from pathlib import Path
from urllib.parse import quote


def build_map_html(javascript_key, workplace=None, radius_km=3.0, stations=None, facilities=None, neighborhood=None, explore=None, geometry=None, age_regions=None):
    radius_km = float(radius_km)
    if not math.isfinite(radius_km) or not 0.5 <= radius_km <= 10:
        raise ValueError("탐색 반경은 0.5~10km여야 합니다.")
    center = {"latitude": 37.5665, "longitude": 126.9780}
    if workplace:
        lat, lon = float(workplace["latitude"]), float(workplace["longitude"])
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("유효한 위도·경도가 필요합니다.")
        center = {"latitude": lat, "longitude": lon}
    if neighborhood:
        lat,lon=float(neighborhood['latitude']),float(neighborhood['longitude'])
        if not (math.isfinite(lat) and math.isfinite(lon) and 37<=lat<=38 and 126<=lon<=128):
            raise ValueError('서울 동네의 유효한 좌표가 필요합니다.')
    payload = json.dumps({"center": center, "workplace": bool(workplace),
                          "age_regions":age_regions or [],"explore":explore,"geometry":geometry,"neighborhood": neighborhood, "stations": stations or [], "facilities": facilities or [], "radius_m": round(radius_km * 1000)}, ensure_ascii=False)
    # HTML의 script 종료 태그를 데이터로 삽입할 수 없게 한다.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    gradient=(Path(__file__).resolve().parent/'map_gradient.js').read_text(encoding='utf-8')
    bikes=(Path(__file__).resolve().parent/'map_bikes.js').read_text(encoding='utf-8')
    return TEMPLATE.replace('__BIKE_CODE__',bikes).replace('__GRADIENT_CODE__',gradient).replace("__KEY__", quote(javascript_key, safe="")).replace("__DATA__", payload)


TEMPLATE = r'''
<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<style>html,body{margin:0;padding:0;font-family:sans-serif}#map{width:100%;height:500px;border-radius:12px}
#error{padding:12px;color:#b91c1c}#error:empty{display:none}</style></head><body>
<div style="padding:8px;background:#f1f5f9;color:#0f172a;font-size:13px">
<label><input type="checkbox" id="layer-bike" checked>따릉이 대여소</label>
<label><input type="checkbox" id="layer-facility" checked>주변 시설</label>
<label>연령 지도 <select id="layer-age"><option value="composition" selected>20~39세 ↔ 60세 이상 구성</option><option value="">기본 영역</option><option value="20">20대 비율</option><option value="30">30대 비율</option><option value="40">40대 비율</option><option value="50">50대 비율</option><option value="60">60대 비율</option></select></label>
<div style="display:flex;align-items:center;gap:8px;margin-top:6px"><span>20~39세 비중 우세</span><span style="display:inline-block;width:130px;height:12px;background:linear-gradient(to right,#16a34a,#facc15,#dc2626)"></span><span>60세 이상 비중 우세</span><span> · 자료 없음: 회색</span></div>
<span id="age-note">선택 동네의 조회된 주민등록 자료만 표시</span></div>
<div id="bike-note" style="padding:3px 8px;background:#f1f5f9;color:#166534;font-size:12px"></div>
<div id="viewport-status" role="status" style="padding:5px 8px;background:#eff6ff;color:#1d4ed8;font-size:12px">지도 화면 범위를 확인하고 있습니다…</div>
<div id="error" role="alert"></div><div id="map" aria-label="직장과 탐색 범위 지도"></div>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KEY__&autoload=false"></script>
<script>
__GRADIENT_CODE__
__BIKE_CODE__
const data = __DATA__;
function fail(){document.getElementById('error').textContent='지도 연결을 확인해주세요. 카카오맵 활성화, JavaScript 키, SDK 등록 도메인을 확인하세요.';}
if(window.kakao && window.kakao.maps){
  kakao.maps.load(function(){
    const center = new kakao.maps.LatLng(data.center.latitude, data.center.longitude);
    const map = new kakao.maps.Map(document.getElementById('map'), {center:center, level:7});
    map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
    const stationInfo = new kakao.maps.InfoWindow({removable:true,zIndex:20});
    const smoothAge=createAgeGradient(map,data);
    const facilityLayers=[],areaLayers=[];
    const comparisonLayers=[];
    const bikeViewport=createBikeViewport(map,stationInfo,data.stations);
    document.getElementById('layer-facility').onchange=function(){facilityLayers.forEach(x=>x.setMap(this.checked?map:null));};
    document.getElementById('layer-age').onchange=function(){
      comparisonLayers.forEach(x=>x.setMap(this.value==='composition'?map:null));
      smoothAge.setEnabled(this.value==='composition');
      if(this.value==='composition'){
        const composition=(data.explore||{}).composition;
        areaLayers.forEach(x=>x.setOptions({fillOpacity:0,strokeOpacity:0}));
        document.getElementById('age-note').textContent=composition?'20~39세 '+composition.young_share+'% / 60세 이상 '+composition.older_share+'% · 주민등록 '+data.explore.month:'연령 구성 자료 없음 (회색)';
        return;
      }
      const rates=(data.explore||{}).age_rates||{};const value=rates[this.value];
      const known=this.value && value!==undefined;
      const color=this.value?(known?'#7c3aed':'#94a3b8'):'#f97316';
      areaLayers.forEach(x=>x.setOptions({strokeOpacity:0,fillColor:color,fillOpacity:known?0.15+Math.min(value,100)/100*0.6:0.15}));
      document.getElementById('age-note').textContent=this.value?(known?this.value+'대 '+value+'% · 주민등록 기준월 '+data.explore.month:'해당 연령 자료 미조회 (회색)'):'선택 동네의 조회된 주민등록 자료만 표시';
    };
    const facilityColors={parking:'#9333ea',subways:'#0284c7',ev_stations:'#16a34a',parks:'#15803d',bikes:'#0d9488'};
    const facilityBounds=new kakao.maps.LatLngBounds();
    (data.facilities || []).forEach(function(facility){
      if(facility.kind==='bikes')return;
      const position=new kakao.maps.LatLng(facility.latitude,facility.longitude);
      facilityBounds.extend(position);
      const color=facilityColors[facility.kind] || '#64748b';
      const dot=new kakao.maps.Circle({map:map,center:position,radius:35,
        strokeColor:color,strokeWeight:2,fillColor:color,fillOpacity:0.85});
      (facility.kind==='bikes'?bikeLayers:facilityLayers).push(dot);
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
    if(data.neighborhood){
      const neighborhood=data.neighborhood;
      const position=new kakao.maps.LatLng(neighborhood.latitude,neighborhood.longitude);
      const marker=new kakao.maps.Marker({map:map,position:position,title:neighborhood.name+' · 동네 대표 위치'});
      const label=document.createElement('div');
      label.style.cssText='padding:6px 10px;background:#c2410c;color:white;border-radius:8px;font-size:13px;white-space:nowrap';
      label.textContent=neighborhood.name+' · 대표점';
      new kakao.maps.CustomOverlay({map:map,position:position,content:label,yAnchor:2.6});
      const showArea=function(){
        const box=document.createElement('div');box.style.cssText='padding:12px;min-width:210px;max-width:310px;white-space:normal;color:#111;background:white';
        const heading=document.createElement('strong');heading.textContent=neighborhood.name+' · '+(data.geometry?'법정동 경계':'경계 자료 없음');box.appendChild(heading);
        ((data.explore||{}).lines||[]).forEach(line=>{const p=document.createElement('p');p.textContent=line;box.appendChild(p);});
        const rates=(data.explore||{}).age_rates||{};Object.keys(rates).forEach(age=>{const p=document.createElement('div');p.textContent=age+'대: '+rates[age]+'%';box.appendChild(p);});
        stationInfo.setContent(box);stationInfo.setPosition(position);stationInfo.open(map);
      };
      if(data.geometry){
        const polygons=data.geometry.type==='MultiPolygon'?data.geometry.coordinates:[data.geometry.coordinates];
        polygons.forEach(rings=>{const path=rings.map(ring=>ring.map(point=>new kakao.maps.LatLng(point[1],point[0])));
          const polygon=new kakao.maps.Polygon({map:map,path:path,strokeWeight:2,strokeColor:'#ea580c',fillColor:'#f97316',fillOpacity:0.15});
          areaLayers.push(polygon);kakao.maps.event.addListener(polygon,'click',showArea);
        });
      }
      label.addEventListener('click',showArea);
      kakao.maps.event.addListener(marker,'click',function(){
        const text=document.createElement('div');
        text.style.cssText='padding:12px;min-width:190px;max-width:280px;white-space:normal';
        text.textContent=neighborhood.name+' · 동네 대표 위치(개별 주택 아님) · 계약월 '+neighborhood.month+' · 예산에 맞는 조회 거래 '+neighborhood.count+'건';
        stationInfo.setContent(text);stationInfo.open(map,marker);
      });
      const bounds=new kakao.maps.LatLngBounds();
      bounds.extend(position);
      if(data.workplace){bounds.extend(center);map.setBounds(bounds);}
      else{map.setCenter(position);map.setLevel(5);}
    }

    const ageBounds=new kakao.maps.LatLngBounds();
    (data.age_regions||[]).forEach(region=>{
      const position=new kakao.maps.LatLng(region.latitude,region.longitude);ageBounds.extend(position);
      if(data.neighborhood && region.code===data.neighborhood.legal_code)return;
      const c=region.composition;
      if(!region.geometry)return;
      const polygons=region.geometry.type==='MultiPolygon'?region.geometry.coordinates:[region.geometry.coordinates];
      polygons.forEach(rings=>{
      const polygon=new kakao.maps.Polygon({map:map,path:rings.map(ring=>ring.map(p=>new kakao.maps.LatLng(p[1],p[0]))),strokeOpacity:0,strokeWeight:0,fillOpacity:0});
      comparisonLayers.push(polygon);
      kakao.maps.event.addListener(polygon,'click',()=>{
        const c=region.composition;
        const box=document.createElement('div');box.style.cssText='padding:12px;max-width:280px;white-space:normal';
        box.textContent=region.name+' · 법정동 경계(2023 자료) · '+region.month+' 주민등록 · '+(c?'20~39세 '+c.young_share+'% / 60세 이상 '+c.older_share+'%':'자료 없음');
        stationInfo.setContent(box);stationInfo.setPosition(position);stationInfo.open(map);
      });
      });
    });
    document.getElementById('layer-age').onchange();
    let lastViewportKey='';
    const viewportKey=bounds=>['south','west','north','east'].map(k=>Number(bounds[k]).toFixed(6)).join(':');
    window.addEventListener('message',event=>{
      if(event.source!==window.parent || event.data.type!=='zipchack:data')return;
      if(event.data.stations)bikeViewport.setStations(event.data.stations);
      const incoming=new Map((event.data.regions||[]).map(r=>[r.code,r]));
      (data.age_regions||[]).forEach(region=>{if(incoming.has(region.code))Object.assign(region,incoming.get(region.code));});
      if(event.data.explore)data.explore=event.data.explore;
      const status=event.data.status;
      if(status && status.bounds && viewportKey(status.bounds)===lastViewportKey){
        document.getElementById('viewport-status').textContent=status.message;
      }
      document.getElementById('layer-age').onchange();
    });
    let viewportTimer;
    function publishViewport(){
      if(!window.parent || typeof map.getBounds!=='function')return;
      const bounds=map.getBounds(),sw=bounds.getSouthWest(),ne=bounds.getNorthEast();
      const viewport={south:sw.getLat(),west:sw.getLng(),north:ne.getLat(),east:ne.getLng()};
      const key=viewportKey(viewport);
      if(key===lastViewportKey)return;
      lastViewportKey=key;
      document.getElementById('viewport-status').textContent='현재 화면의 연령 자료 조회 중… 회색 영역은 조회 완료 후 갱신됩니다.';
      window.parent.postMessage({type:'zipchack:viewport',viewport:viewport},'*');
    }
    kakao.maps.event.addListener(map,'idle',()=>{
      window.clearTimeout(viewportTimer);viewportTimer=window.setTimeout(publishViewport,500);
    });
    if(window.parent && typeof window.parent.postMessage==='function'){
      window.parent.postMessage({type:'zipchack:ready'},'*');window.setTimeout(publishViewport,650);
    }
  });
}else{fail();}
</script></body></html>
'''
