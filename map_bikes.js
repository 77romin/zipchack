// 공식 위치 스냅샷을 화면 범위로 필터링한다. 이동마다 외부 API를 호출하지 않는다.
function createBikeViewport(map,stationInfo,initialStations){
  let stations=[],signature='';const markers=new Map();const limit=400;
  function update(){
    const enabled=document.getElementById('layer-bike').checked;
    const bounds=typeof map.getBounds==='function'?map.getBounds():null;
    const sw=bounds?bounds.getSouthWest():null,ne=bounds?bounds.getNorthEast():null;
    const visible=stations.filter(s=>!bounds||(s.latitude>=sw.getLat()&&s.latitude<=ne.getLat()&&s.longitude>=sw.getLng()&&s.longitude<=ne.getLng()));
    const shown=enabled?visible.slice(0,limit):[];const active=new Set();
    shown.forEach(station=>{
      const key=String(station.id||station.latitude+':'+station.longitude);active.add(key);
      let marker=markers.get(key);
      if(!marker){
        const icon=document.createElement('button');icon.type='button';
        icon.title='따릉이 · '+station.name;icon.setAttribute('aria-label',icon.title);
        icon.style.cssText='width:23px;height:23px;background:#15803d;border:1px solid white;border-radius:50%;padding:2px;box-shadow:0 1px 3px #555;cursor:pointer';
        icon.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="white" stroke-width="1.8"><circle cx="5.5" cy="16.5" r="4"/><circle cx="18.5" cy="16.5" r="4"/><path d="M5.5 16.5L10 8l5 8.5H5.5L9 10h8l1.5 6.5M8 6h4m3-2h3l2 5"/></svg>';
        marker=new kakao.maps.CustomOverlay({map:null,content:icon,zIndex:5,position:new kakao.maps.LatLng(station.latitude,station.longitude)});
        markers.set(key,marker);
        icon.addEventListener('click',()=>{
          const text=document.createElement('div');text.style.cssText='padding:12px;max-width:260px;white-space:normal';
          text.textContent='따릉이 '+station.name+' · 대여소 위치 자료 · 실시간 자전거 재고 아님';
          stationInfo.setContent(text);stationInfo.setPosition(new kakao.maps.LatLng(station.latitude,station.longitude));stationInfo.open(map);
        });
      }
      marker.setMap(map);
    });
    markers.forEach((marker,key)=>{if(!active.has(key))marker.setMap(null);});
    document.getElementById('bike-note').textContent=enabled?'화면 안 따릉이 '+shown.length+'/'+visible.length+'곳'+(visible.length>limit?' · 지도를 확대하면 나머지 대여소도 볼 수 있어요.':''):'따릉이 표시 꺼짐';
  }
  function setStations(next){
    const nextSignature=JSON.stringify(next||[]);
    if(signature!==nextSignature){markers.forEach(marker=>marker.setMap(null));markers.clear();stations=next||[];signature=nextSignature;}
    update();
  }
  document.getElementById('layer-bike').onchange=update;
  kakao.maps.event.addListener(map,'idle',update);
  setStations(initialStations);
  return {update,setStations};
}
