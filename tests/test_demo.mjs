import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

// DOM contract harness: exercises actual inline JS, not a second filter implementation.
// Does not replace browser rendering/layout checks.
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.listeners={};this.value='';this.checked=false;this._text='';}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(x=>typeof x==='string'?x:x.textContent).join('');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=nodes;}
  addEventListener(type,fn){this.listeners[type]=fn;}
  remove(){}
  click(){this.listeners.click?.();}
}
function setup(){
 const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
 const html=fs.readFileSync(path.join(root,'docs/index.html'),'utf8');
 const data=html.match(/<script id="history-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
 const source=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
 const ids=['budget','people','drinks','results','count','export-status','case-button','case-result','export','hero-price','hero-desc','history-data'];
 const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));
 nodes.budget.value='50';nodes.people.value='2';nodes['history-data'].textContent=data;
 let exported;
 const context={document:{getElementById:id=>{assert.ok(nodes[id],id);return nodes[id];},createElement:tag=>new Element(tag),body:new Element('body')},
  Blob, URL:{createObjectURL:blob=>{exported=blob;return 'blob:test';},revokeObjectURL:()=>{}},setTimeout:fn=>fn()};
 vm.runInNewContext(source,context);
 return {nodes,change(id,value){nodes[id].value=value;nodes[id].listeners.input();},checkDrinks(value){nodes.drinks.checked=value;nodes.drinks.listeners.input();},getExport:()=>exported};
}

test('historical page responds to budget, people and drinks',()=>{
 const ui=setup(),n=ui.nodes;
 assert.equal(n.results.children.length,3);
 assert.match(n.results.children[0].textContent,/22\.00/);
 ui.checkDrinks(true);
 assert.equal(n.results.children.length,3);
 assert.match(n.results.children[0].textContent,/39\.00/);
 ui.change('budget','40');assert.equal(n.results.children.length,1);
 ui.change('budget','10');assert.match(n.results.textContent,/没有满足条件/);
 ui.change('budget','50');ui.change('people','3');assert.match(n.results.textContent,/没有满足条件/);
 ui.change('people','2');ui.change('budget','0.001');assert.match(n.results.textContent,/有效的总预算/);
});

test('negative example is labeled synthetic and exports stay historical',async()=>{
 const ui=setup();ui.nodes['case-button'].click();
 assert.match(ui.nodes['case-result'].textContent,/合成反例/);
 ui.nodes.export.click();
 const data=JSON.parse(await ui.getExport().text());
 assert.equal(data.mode,'historical-replay-not-live');
 assert.equal(data.quotes.length,3);
 assert.equal(data.people,2);
 assert.ok(data.quotes.every(q=>!('raw_evidence' in q)));
});
