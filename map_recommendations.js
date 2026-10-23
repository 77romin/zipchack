function createRecommendations(map,showCard,initial,onChange){
  let signature='';let layers=[];
  function update(rows){
    const next=JSON.stringify(rows||[]);if(next===signature)return;signature=next;
    if(onChange)onChange();
    layers.forEach(layer=>layer.setMap(null));layers=[];
    const bounds=new kakao.maps.LatLngBounds();let count=0;
    (rows||[]).forEach(row=>{
      const point=row.point;if(!point||!Number.isFinite(point.latitude)||!Number.isFinite(point.longitude))return;
      const button=document.createElement('button');button.type='button';
      button.textContent=row.label;button.title=row.dong+' · '+row.label+(row.label==='후보'?'':'위');button.setAttribute('aria-label',button.title);
      const color=row.label==='후보'?'#475569':row.provisional?'#b45309':'#2563eb';
      button.style.cssText='padding:6px 9px;border:2px solid white;border-radius:18px;color:white;background:'+color+';box-shadow:0 1px 4px #555;font-weight:bold;cursor:pointer';
      const position=new kakao.maps.LatLng(point.latitude,point.longitude);bounds.extend(position);count++;
      const layer=new kakao.maps.CustomOverlay({map,position,content:button,zIndex:12,clickable:true,yAnchor:1.5});layers.push(layer);
      button.addEventListener('click',()=>showCard(row,position));
    });
    document.getElementById('recommendation-note').textContent=count?'예산 후보 '+count+'곳 · 번호는 생활 선호 비교 · 참고는 자료 제한 있음 · 현재 매물·통근 검증 아님':'';
    if(count){map.setBounds(bounds);if(count===1)map.setLevel(5);}
  }
  update(initial);return {update};
}
