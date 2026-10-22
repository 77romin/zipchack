// Kakao/DOM stub으로 초기 연령 필터·대여소·영역 클릭 이벤트 실행 검증.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8');
const elements=new Map();const objects=[];const events=[];
function el(){return {value:'20',checked:true,style:{},appendChild(){},addEventListener(){},textContent:''};}
const document={getElementById(id){if(!elements.has(id))elements.set(id,el());return elements.get(id);},createElement:el};
class Shape{constructor(options){this.options=options;objects.push(this);}setMap(map){this.map=map;}setOptions(options){Object.assign(this.options,options);}getBounds(){return {};}setContent(content){this.content=content;}setPosition(){}open(){}}
class MapObject{addControl(){}setBounds(){}setCenter(){}setLevel(){}}
const maps={load:f=>f(),LatLng:class{},Map:MapObject,ZoomControl:class{},ControlPosition:{RIGHT:1},Marker:Shape,Circle:Shape,Polygon:Shape,InfoWindow:Shape,CustomOverlay:Shape,LatLngBounds:class{extend(){}},event:{addListener(object,type,callback){events.push({object,type,callback});}}};
vm.runInNewContext(source,{window:{kakao:{maps}},kakao:{maps},document,console});
assert(elements.get('age-note').textContent.includes('11'));
elements.get('layer-bike').checked=false;elements.get('layer-bike').onchange();
const area=events.find(e=>e.object.options?.radius===500);assert(area);area.callback();
assert(objects.some(o=>o.content));
console.log('지도 초기 연령 색상·대여소 필터·영역 클릭 실행 통과');
