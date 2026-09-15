const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/index.html','utf8');
let js=html.split('<script>')[1].split('</script>')[0];new vm.Script(js);
function harness(saved={},width=390,height=844){
 const elements={},storage=new Map(Object.entries(saved)),timers=new Map();let timerId=0;
 const ctx=new Proxy({measureText(t){return {width:t.length*5}}},{get(t,k){return k in t?t[k]:(()=>{})},set(t,k,v){t[k]=v;return true}});
 function el(id){return elements[id]||(elements[id]={id,hidden:false,style:{setProperty(){}},classList:{add(){},remove(){}},children:[],getContext(){return ctx},getBoundingClientRect(){return id==='hud'?{bottom:62}:width>=900?{left:width-380,top:62}:{left:0,top:height-325}},append(x){this.children.push(x)},replaceChildren(){this.children=[]},setAttribute(){},addEventListener(){},showModal(){this.open=true},close(){this.open=false}})}
 const doc={getElementById:el,createElement:()=>el('new'+Math.random()),querySelector:()=>null,addEventListener(){}};
 const sandbox={document:doc,window:{},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},innerWidth:width,innerHeight:height,devicePixelRatio:1,performance:{now:()=>0},matchMedia:()=>({matches:true}),addEventListener(){},setTimeout:(fn)=>{timers.set(++timerId,fn);return timerId},clearTimeout:id=>timers.delete(id),requestAnimationFrame:()=>0,cancelAnimationFrame(){},console};
 const injected=js.replace(/\}\)\(\);\s*$/,'globalThis.test={levelAt,levelGoal,resetState,resume,expand,frontier,nextNear,canPlace,select,type,check,hint,showMenu,load,saveNow,recordRun,fitClue,cells,eligible,pack,get(){return {words,board,clues,byId,coins,score,points,selected,buffer,cursor,records,revealed,DATA,menuOpen}}};})();');
 vm.runInNewContext(injected,sandbox);
 return {api:sandbox.test,storage,elements,timers,flush(){for(const [id,fn]of [...timers]){timers.delete(id);fn()}}};
}
const a=harness();a.api.resetState();a.api.resume();
let state=a.api.get();assert(state.DATA.length>1000);
assert(new Set(state.DATA.map(e=>e[0])).size===state.DATA.length);
assert(state.DATA.every(e=>/^[А-Я]+$/.test(e[0])&&e[1]&&e[2]>=1&&e[2]<=10));
let count=0;
const t0=Date.now();
for(;count<300;count++){
 state=a.api.get();
 const w=state.words.find(a.api.eligible);assert(w,'frontier exhausted at '+count);
 a.api.select(w.id);
 for(let i=0;i<40&&a.api.get().selected?.id===w.id&&!w.solved;i++){
  const s=a.api.get();if(s.buffer.every(Boolean)){a.api.check();break}
  a.api.type(w.a[s.cursor]);a.flush();
 }
 a.flush();assert(w.solved,'word not solved');
}
state=a.api.get();assert.equal(state.score,300);assert.equal(state.coins,312);
for(const [answers,level] of [[0,0],[19,0],[20,1],[59,1],[60,2],[119,2],[120,3],[200,4]])assert.equal(a.api.levelAt(answers),level);
assert.equal(a.api.levelGoal(0),20);assert.equal(a.api.levelGoal(1),60);assert.equal(a.api.levelGoal(2),120);
for(const w of state.words){
 for(const [x,y,i]of a.api.cells(w)){assert.equal(state.board.get(x+','+y).c,w.a[i]);assert(!state.clues.has(x+','+y))}
}
a.api.saveNow();const b=harness(Object.fromEntries(a.storage));assert.equal(b.api.get().score,300);assert.equal(b.api.get().words.length,state.words.length);
const w=b.api.get().words.find(b.api.eligible);b.api.resume();b.api.select(w.id);b.api.hint();assert(b.api.get().revealed.size>0);b.api.saveNow();
const c=harness(Object.fromEntries(b.storage));assert.equal(c.api.get().revealed.size,b.api.get().revealed.size);
c.api.recordRun();c.api.recordRun();assert.equal(c.api.get().records.length,1);
c.api.resetState();assert.equal(c.api.get().revealed.size,0);assert.equal(c.api.get().score,0);assert.equal(c.api.get().coins,12);
const d=harness();d.api.resetState();d.api.resume();let candidates=d.api.get().words.filter(d.api.eligible);
d.api.select(candidates[0].id);const ww=candidates[0];
while(d.api.get().buffer.some(v=>!v))d.api.type(ww.a[d.api.get().cursor]);
d.api.select(candidates[1].id);d.flush();assert.equal(d.api.get().score,0);
d.api.showMenu();d.flush();assert(d.api.get().menuOpen);
const e=harness();e.api.resetState();e.api.resume();
const available=e.api.get().words.filter(e.api.eligible);e.api.select(available[0].id);
e.elements.next.onclick();assert.notEqual(e.api.get().selected.id,available[0].id,'Other must change selection');
function solveSelected(h){const w=h.api.get().selected;while(h.api.get().buffer.some(v=>!v))h.api.type(w.a[h.api.get().cursor]);h.api.check();h.flush();assert(w.solved)}
let oldCoins=e.api.get().coins;e.api.check();solveSelected(e);assert.equal(e.api.get().coins,oldCoins,'No coin after mistake');
oldCoins=e.api.get().coins;e.api.hint();assert.equal(e.api.get().coins,oldCoins-3);solveSelected(e);assert.equal(e.api.get().coins,oldCoins-3,'No coin after hint');
e.api.saveNow();const saved=e.api.pack();assert.equal(saved.score,2);
for(const [width,height]of [[320,568],[390,844],[430,932],[844,390],[1366,768]]){
 const mobile=harness({},width,height);mobile.api.resetState();mobile.api.resume();
 const word=mobile.api.get().words.find(mobile.api.eligible);mobile.api.select(word.id);
 assert(mobile.api.get().buffer.length===word.a.length);
 mobile.api.hint();mobile.api.saveNow();
 const restored=harness(Object.fromEntries(mobile.storage),width,height);restored.api.resume();
 assert(restored.api.get().selected);assert(restored.api.get().selected.hinted);
}
console.log(JSON.stringify({questions:state.DATA.length,answers:count,generated:state.words.length,seconds:(Date.now()-t0)/1000,checks:'geometry, save/load, hints reset, record deduplication, stale answer, menu'},null,2));
