const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements=new Map();function element(){return {checked:true,style:{},setAttribute(){},addEventListener(){},textContent:''};}
const document={getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id);},createElement:element};
let west=126.9,east=127.0,created=0;const layers=[],events=[];
const map={getBounds(){return {getSouthWest:()=>({getLat:()=>37,getLng:()=>west}),getNorthEast:()=>({getLat:()=>38,getLng:()=>east})};}};
const kakao={maps:{LatLng:class{},CustomOverlay:class{constructor(){created++;layers.push(this);}setMap(value){this.map=value;}},event:{addListener(m,type,fn){events.push(fn);}}}};
const context={document,kakao,Map,Set};vm.runInNewContext(fs.readFileSync('map_bikes.js','utf8'),context);
const stations=[{id:'a',name:'동쪽',latitude:37.5,longitude:126.95},{id:'b',name:'서쪽',latitude:37.5,longitude:126.8}];
const viewport=context.createBikeViewport(map,{},stations);
assert.equal(created,1);assert.equal(elements.get('bike-note').textContent,'화면 안 따릉이 1/1곳');
west=126.75;east=126.85;events[0]();assert.equal(created,2);assert.equal(layers.filter(x=>x.map).length,1);
west=126.9;east=127.;events[0]();assert.equal(created,2,'이미 만든 마커는 재사용');
elements.get('layer-bike').checked=false;elements.get('layer-bike').onchange();assert.equal(layers.filter(x=>x.map).length,0);
elements.get('layer-bike').checked=true;viewport.setStations([{id:'c',name:'교체',latitude:37.5,longitude:126.96}]);assert.equal(layers.filter(x=>x.map).length,1);
viewport.setStations(Array.from({length:450},(_,i)=>({id:'s'+i,name:'대여소',latitude:37.5,longitude:126.95})));
assert.equal(layers.filter(x=>x.map).length,400);assert(elements.get('bike-note').textContent.includes('400/450'));
console.log('지도 이동에 따른 대여소 교체·마커 재사용·필터·자료 교체·표시 상한 통과');
