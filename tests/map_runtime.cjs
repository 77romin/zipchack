// Kakao/DOM stub으로 초기 연령 필터·대여소·영역 클릭 이벤트 실행 검증.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8');
const elements=new Map();const objects=[];const events=[];const canvasOps=[];
function el(kind){const result={value:'20',checked:true,clientWidth:800,clientHeight:500,style:{},appendChild(){},setAttribute(){},addEventListener(){},textContent:''};
 if(kind==='canvas')result.getContext=()=>new Proxy({beginPath(){},moveTo(){},lineTo(){},closePath(){},fill(rule){canvasOps.push(['fill',rule]);},drawImage(){canvasOps.push(['drawImage']);}}, {set(target,key,value){canvasOps.push([key,value]);target[key]=value;return true;}});
 return result;}
const document={getElementById(id){if(!elements.has(id))elements.set(id,el());return elements.get(id);},createElement:el};
class Shape{constructor(options){this.options=options;objects.push(this);}setMap(map){this.map=map;}setOptions(options){Object.assign(this.options,options);}getBounds(){return {};}setContent(content){this.content=content;}setPosition(){}open(){}}
class MapObject{addControl(){}setBounds(){}setCenter(){}setLevel(){}getCenter(){return {};}getProjection(){return {containerPointFromCoords:p=>({x:p.lon,y:p.lat})};}}
const maps={load:f=>f(),LatLng:class{constructor(lat,lon){this.lat=lat;this.lon=lon;}},Map:MapObject,ZoomControl:class{},ControlPosition:{RIGHT:1},Marker:Shape,Circle:Shape,Polygon:Shape,InfoWindow:Shape,CustomOverlay:Shape,LatLngBounds:class{extend(){}},event:{addListener(object,type,callback){events.push({object,type,callback});}}};
vm.runInNewContext(source,{window:{kakao:{maps}},kakao:{maps},document,console});
assert(elements.get('age-note').textContent.includes('11'));
elements.get('layer-bike').checked=false;elements.get('layer-bike').onchange();
const area=events.find(e=>Array.isArray(e.object.options?.path));assert(area);area.callback();
assert(objects.some(o=>o.content));
elements.get('layer-age').value='composition';elements.get('layer-age').onchange();
assert(canvasOps.some(op=>op[0]==='filter' && op[1]==='blur(24px)'));
assert(canvasOps.some(op=>op[0]==='globalCompositeOperation' && op[1]==='destination-in'));
assert(objects.filter(o=>o.options?.path).every(o=>o.options.strokeOpacity===0));
console.log('지도 초기 연령 색상·대여소 필터·영역 클릭 실행 통과');
