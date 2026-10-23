export default function(component) {
 const {parentElement,data,setStateValue}=component;
 let frame=parentElement.querySelector('iframe');
 if(!frame){frame=document.createElement('iframe');frame.title='집착 지도';frame.style.cssText='width:100%;height:575px;border:0';parentElement.appendChild(frame);}
 const update=()=>frame.contentWindow.postMessage({type:'zipchack:data',regions:data.regions,explore:data.explore,status:data.status,stations:data.stations},'*');
 const receive=event=>{
  if(event.source!==frame.contentWindow)return;
  if(event.data.type==='zipchack:ready')update();
  if(event.data.type==='zipchack:viewport')setStateValue('viewport',event.data.viewport);
 };
 window.addEventListener('message',receive);
 if(frame.dataset.navigation!==data.navigation){frame.dataset.navigation=data.navigation;frame.srcdoc=data.html;}else update();
 return ()=>window.removeEventListener('message',receive);
}
