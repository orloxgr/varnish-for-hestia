// Exercise the shipped editors in a dependency-free DOM harness. No visual claim.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

const product=process.argv[2];
assert.ok(['hestia','webuzo'].includes(product),'Choose hestia or webuzo');
class Element {
  constructor(tag,text=''){this.tagName=tag;this.children=[];this.attrs={};this.dataset={};this.style={};this.events={};this._text=text;}
  append(...nodes){for(let n of nodes){if(typeof n==='string')n=new Element('#text',n);n.parentElement=this;this.children.push(n);}}
  replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
  set value(v){this._value=String(v);}
  get value(){return this._value??(this.tagName==='select'?(this.children.find(c=>c.selected)??this.children[0])?.value??'':'');}
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return this.attrs[k];}
  addEventListener(k,f){(this.events[k]??=[]).push(f);}
  querySelectorAll(selector){const all=this.children.flatMap(c=>[c,...c.querySelectorAll('*')]);if(selector==='*')return all;return all.filter(n=>selector.split(',').includes(n.tagName));}
  querySelector(selector){return this.querySelectorAll(selector)[0]??null;}
  async fire(type){const e={target:this,preventDefault(){this.prevented=true;}};if(this['on'+type])await this['on'+type](e);for(const f of this.events[type]??[])await f(e);assert.ok(!e.prevented,'Unexpected validation rejection');}
  click(){return this.fire('click');}
  focus(){}
}
class Option extends Element {constructor(text,value){super('option',text);this.value=value;}}
const ids=new Map(),root=new Element('div');
const document={createElement:t=>new Element(t),createTextNode:t=>new Element('#text',t),getElementById:id=>ids.get(id),querySelectorAll:()=>[]};
const labels={basic:'Basic',ultracache:'UltraCache'};
const row={id:'policy:comment-author-prefix',name:'comment_author_*',match:{kind:'prefix',value:'comment_author_'},description:'Commenter identity',provider:'WordPress',default_version:'2026.11.20.5',inherited_exists:true,sources:[],profile_actions:{}};
for(const [p,action] of Object.entries({basic:'private',ultracache:'shared'}))row.profile_actions[p]={action,proposal:action,inherited_action:action,inherited_scope:'bundled',scope:'bundled',override:false,active_rule:true,effective_action:action,reset_metadata:{proposal:action,effective_action:action}};
const initial={rows:[row],settings:{schemaVersion:2,rules:[]},scope:'site',profile:'basic'};
const window={addEventListener(){},confirm:()=>true};let submitted;
const context={document,window,Option,TextEncoder,structuredClone,crypto:{randomUUID},console,URL,Blob};
const find=(tag,text)=>root.querySelectorAll(tag).find(n=>n.textContent===text);
if(product==='hestia'){
  for(const id of ['cookie-initial','cookie-rows','cookie-page','cookie-count','cookie-error','cookie-payload','cookie-form','cookie-search','cookie-action-filter-basic','cookie-action-filter-ultracache','cookie-source-filter','cookie-page-size','cookie-select-page','cookie-prev','cookie-next','cookie-add','cookie-bulk-action','cookie-paste','cookie-import',...['basic','ultracache'].flatMap(p=>['cookie-bulk-','cookie-reset-','cookie-suggest-'].map(x=>x+p))]){
    const n=new Element(id==='cookie-rows'?'tbody':id==='cookie-form'?'form':'div');ids.set(id,n);root.append(n);
  }
  ids.get('cookie-initial').textContent=JSON.stringify(initial);ids.get('cookie-page-size').value='100';ids.get('cookie-source-filter').value='';for(const p of ['basic','ultracache'])ids.get('cookie-action-filter-'+p).value='';ids.get('cookie-search').value='';
} else {
  context.window.WebuzoCookiePolicies=undefined;
}
vm.runInNewContext(fs.readFileSync('panel/cookie-admin.js','utf8'),context);
if(product==='webuzo'){
  const model={...initial,administrator:true,id:'a'.repeat(32),sites:[{id:'a'.repeat(32),domain:'example.test',owner:'alice'}],enabled:true,integration:{enabled:false,url:'https://example.test/wp-json/ultracache/v1/cookie-policy-control'}};
  window.WebuzoCookiePolicies.mount(root,async(action,values)=>{
    if(action==='cookie_policies_save'){submitted=structuredClone(values.settings);model.settings=submitted;}
    return {cookie_policies:structuredClone(model)};
  });
  await new Promise(resolve=>setImmediate(resolve));
}
const select=p=>root.querySelectorAll('select').find(n=>n.getAttribute('aria-label')===labels[p]+' action for comment_author_*');
const reset=p=>select(p).parentElement.children.find(n=>n.tagName==='button'&&n.textContent==='Reset '+labels[p]);
async function save(){if(product==='hestia'){await ids.get('cookie-form').fire('submit');submitted=JSON.parse(ids.get('cookie-payload').value);}else await find('button','Save & Apply cookie policies').fire('click');return submitted;}
for(const p of ['basic','ultracache'])assert.deepEqual(Array.from(select(p).children,n=>n.value),['shared','variant','private']);
assert.equal(select('basic').value,'private');assert.equal(select('ultracache').value,'shared');
select('basic').value='variant';await select('basic').fire('change');
assert.equal(select('basic').value,'variant');assert.equal(select('ultracache').value,'shared');
select('ultracache').value='private';await select('ultracache').fire('change');
await reset('basic').fire('click');
assert.equal(select('basic').value,'private');assert.equal(select('ultracache').value,'private');
let payload=await save();assert.equal(payload.schemaVersion,2);assert.equal(payload.rules.length,1);
assert.deepEqual(payload.rules[0].actions,{basic:null,ultracache:'private'});
await reset('ultracache').fire('click');
assert.equal(select('basic').value,'private');assert.equal(select('ultracache').value,'shared');
assert.equal((await save()).rules.length,0);
const tbody=product==='hestia'?ids.get('cookie-rows'):root.querySelector('tbody');
const checkbox=tbody.querySelectorAll('input').find(n=>n.type==='checkbox');
checkbox.checked=true;await checkbox.fire('change');
const bulk=product==='hestia'?ids.get('cookie-bulk-action'):root.querySelectorAll('select').find(n=>n.getAttribute('aria-label')==='Action for selected cookies');
bulk.value='variant';await (product==='hestia'?ids.get('cookie-bulk-basic'):find('button','Apply to Basic')).fire('click');
assert.equal(select('basic').value,'variant');assert.equal(select('ultracache').value,'shared');
assert.deepEqual((await save()).rules[0].actions,{basic:'variant',ultracache:null});
await reset('basic').fire('click');await save();
const paste=product==='hestia'?ids.get('cookie-paste'):root.querySelectorAll('textarea').find(n=>n.getAttribute('aria-label')==='Paste cookie policy rows from Excel');
paste.value='my_cookie\tIndependent columns\tvariant\tprivate'.replaceAll('\\t','\t');
await (product==='hestia'?ids.get('cookie-import'):find('button','Append pasted rows')).fire('click');
payload=await save();const added=payload.rules.find(r=>r.match.value==='my_cookie');
assert.ok(added,'Paste did not preserve tab-separated columns');assert.deepEqual(added.actions,{basic:'variant',ultracache:'private'});
console.log(product+': two columns, three choices, isolated edits/reset, schema2 save and four-column paste passed');


if (product === 'hestia') {
  // Reload the actual editor with every Basic / UltraCache combination.
  const actions = ['shared','variant','private'], filterRows = [];
  for (const basic of actions) for (const ultracache of actions) for (let index=0; index<3; index++) {
    const fixture=structuredClone(row);
    fixture.id=`filter:${basic}:${ultracache}:${index}`;
    fixture.name=`cookie_${basic}_${ultracache}_${index}`;
    fixture.match={kind:'exact',value:fixture.name};
    for (const [profile,action] of Object.entries({basic,ultracache})) {
      fixture.profile_actions[profile]={...fixture.profile_actions[profile],action,proposal:action,inherited_action:action,effective_action:action};
    }
    filterRows.push(fixture);
  }
  for (const [id,old] of ids) {
    const fresh=new Element(old.tagName);ids.set(id,fresh);
  }
  root.replaceChildren(...ids.values());
  ids.get('cookie-initial').textContent=JSON.stringify({...initial,rows:filterRows});
  ids.get('cookie-page-size').value='25';
  ids.get('cookie-search').value='';ids.get('cookie-source-filter').value='';
  const filters=Object.fromEntries(['basic','ultracache'].map(p=>[p,ids.get('cookie-action-filter-'+p)]));
  for (const filter of Object.values(filters)) filter.value='';
  vm.runInNewContext(fs.readFileSync('panel/cookie-admin.js','utf8'),context);
  const visibleNames=()=>ids.get('cookie-rows').querySelectorAll('input').filter(n=>n.type==='text').map(n=>n.value);
  const setFilter=async(profile,value)=>{filters[profile].value=value;await filters[profile].fire('input');};
  await ids.get('cookie-next').fire('click');assert.equal(visibleNames().length,2);
  await setFilter('ultracache','shared');
  assert.equal(visibleNames().length,9,'Changing a profile filter must return to the first page');
  assert.equal(ids.get('cookie-page').textContent,'Page 1 / 1');
  for (const profile of ['basic','ultracache']) for (const action of actions) {
    await setFilter(profile==='basic'?'ultracache':'basic','');await setFilter(profile,action);
    assert.equal(visibleNames().length,9);
    assert.ok(visibleNames().every(name=>name.split('_')[profile==='basic'?1:2]===action));
  }
  await setFilter('basic','private');await setFilter('ultracache','shared');
  assert.equal(visibleNames().length,3,'Both selected profile columns must match the same row');
  await setFilter('basic','');
  assert.equal(visibleNames().length,9);
  assert.ok(visibleNames().includes('cookie_private_shared_0'),'UltraCache Shared must include Basic Private');
  ids.get('cookie-search').value='cookie_private';await ids.get('cookie-search').fire('input');
  assert.equal(visibleNames().length,3,'Search must combine with the profile filters');
  assert.equal((await save()).rules.length,0,'Filtering must not change any policy');
  const action=ids.get('cookie-rows').querySelectorAll('select').find(n=>n.getAttribute('aria-label')==='UltraCache action for cookie_private_shared_0');
  action.value='private';await action.fire('change');
  assert.equal(visibleNames().length,2,'Filters must use the current draft action');
  ids.get('cookie-source-filter').value='local';await ids.get('cookie-source-filter').fire('input');
  assert.equal(visibleNames().length,0,'Source and action filters must both match');
  await setFilter('ultracache','private');assert.deepEqual(visibleNames(),['cookie_private_shared_0']);
  ids.get('cookie-paste').value='pasted_cookie\tIndependent columns\tshared\tvariant';
  await ids.get('cookie-import').fire('click');
  assert.ok(visibleNames().includes('pasted_cookie'),'Pasted rows must be visible despite previous action filters');
  for (const filter of Object.values(filters)) assert.equal(filter.value,'');
  await setFilter('basic','private');await setFilter('ultracache','private');
  await ids.get('cookie-add').fire('click');
  for (const filter of Object.values(filters)) assert.equal(filter.value,'');
  assert.ok(visibleNames().includes(''),'New rows must be visible despite previous action filters');
  console.log('hestia: independent profile filters, all three actions, combined search/source/draft matches, pagination reset and visible added/pasted rows passed');
}
