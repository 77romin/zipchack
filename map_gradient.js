// 동별 원자료를 바꾸지 않는 시각적 평활화. 미확인 영역은 보간하지 않는다.
function createAgeGradient(map, data) {
  const holder=document.createElement('div');
  holder.style.cssText='pointer-events:none;line-height:0';
  const canvas=document.createElement('canvas');holder.appendChild(canvas);
  const overlay=new kakao.maps.CustomOverlay({map:map,content:holder,xAnchor:0.5,yAnchor:0.5,zIndex:1});
  let enabled=false;
  const regions=(data.age_regions||[]).filter(r=>r.geometry);
  if(data.geometry && data.neighborhood && !regions.some(r=>r.code===data.neighborhood.legal_code)){
    regions.push({geometry:data.geometry,composition:(data.explore||{}).composition});
  }
  function polygons(geometry){return geometry.type==='MultiPolygon'?geometry.coordinates:[geometry.coordinates];}
  function paint(context, region, projection, color){
    context.fillStyle=color;
    polygons(region.geometry).forEach(rings=>{
      context.beginPath();
      rings.forEach(ring=>{
        ring.forEach((coord,i)=>{
          const p=projection.containerPointFromCoords(new kakao.maps.LatLng(coord[1],coord[0]));
          if(i===0)context.moveTo(p.x,p.y);else context.lineTo(p.x,p.y);
        });context.closePath();
      });context.fill('evenodd');
    });
  }
  function render(){
    holder.style.display=enabled?'block':'none';
    if(!enabled || typeof map.getProjection!=='function')return;
    const node=document.getElementById('map');
    const width=node.clientWidth,height=node.clientHeight;
    if(!width || !height)return;
    canvas.width=width;canvas.height=height;
    holder.style.width=width+'px';holder.style.height=height+'px';
    overlay.setPosition(map.getCenter());
    const ctx=canvas.getContext('2d'),projection=map.getProjection();
    const raw=document.createElement('canvas'),mask=document.createElement('canvas');
    raw.width=mask.width=width;raw.height=mask.height=height;
    const rawCtx=raw.getContext('2d'),maskCtx=mask.getContext('2d');
    regions.forEach(region=>{
      if(region.composition){paint(rawCtx,region,projection,region.composition.color);paint(maskCtx,region,projection,'white');}
      else paint(ctx,region,projection,'rgba(148,163,184,0.45)');
    });
    // 경계선을 지우고 인접 동의 색을 화면상 24px 범위에서 혼합한다.
    const smooth=document.createElement('canvas');smooth.width=width;smooth.height=height;
    const sc=smooth.getContext('2d');sc.filter='blur(24px)';sc.drawImage(raw,0,0);sc.filter='none';
    // 자료가 있는 동들의 합집합으로 제한: 미확인 동·영역 밖은 색을 채우지 않는다.
    sc.globalCompositeOperation='destination-in';sc.drawImage(mask,0,0);
    ctx.globalAlpha=0.48;ctx.drawImage(smooth,0,0);ctx.globalAlpha=1;
  }
  kakao.maps.event.addListener(map,'idle',render);
  kakao.maps.event.addListener(map,'zoom_start',()=>{holder.style.display='none';});
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(render).observe(document.getElementById('map'));
  return {setEnabled(value){enabled=value;render();}};
}
