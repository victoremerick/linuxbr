// Browser event regressions: an SPA may replace a document before metadata arrives.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {webcrypto} from 'node:crypto';
const root=new URL('../packages/linuxbr-system/files/usr/share/linuxbr/webapps/',import.meta.url);
const catalog=JSON.parse(fs.readFileSync(new URL('catalog.json',root)));
const listeners={};const event=name=>({addListener:callback=>{listeners[name]=callback;}});
const memory=()=>{const state={};return {
  async get(keys){return keys===null?{...state}:Object.fromEntries((Array.isArray(keys)?keys:[keys]).filter(k=>k in state).map(k=>[k,state[k]]));},
  async set(data){Object.assign(state,data);},async remove(key){delete state[key];},async clear(){for(const key of Object.keys(state))delete state[key];}
};};
let tab={id:1,url:'https://open.spotify.com/intl-pt/',active:true,windowId:1,incognito:false};
let offers=0;
if(!globalThis.crypto)Object.defineProperty(globalThis,'crypto',{value:webcrypto});
globalThis.fetch=async()=>({json:async()=>catalog});
globalThis.chrome={
  runtime:{getURL:path=>'chrome-extension://test/'+path,onMessage:event('message'),
    sendNativeMessage:async()=>({installed:false,native_installed:false})},
  storage:{local:memory(),session:memory()},
  tabs:{onRemoved:event('removed'),onUpdated:event('updated'),onActivated:event('activated'),
    get:async()=>({...tab}),query:async()=>[{...tab}],sendMessage:async()=>{throw new Error('document replaced');}},
  windows:{onFocusChanged:event('focused'),WINDOW_ID_NONE:-1,get:async()=>({focused:true})},
  action:{setBadgeBackgroundColor:async()=>{},setBadgeText:async()=>{},setTitle:async()=>{}},
  notifications:{create:async()=>{offers++;},getAll:async()=>({}),clear:async()=>{},
    onClicked:event('clicked'),onButtonClicked:event('button'),onClosed:event('closed')}
};
const rules='data:text/javascript;base64,'+Buffer.from(fs.readFileSync(new URL('rules.js',root))).toString('base64');
const background=fs.readFileSync(new URL('background.js',root),'utf8').replace("'./rules.js'",JSON.stringify(rules));
await import('data:text/javascript;base64,'+Buffer.from(background).toString('base64'));
const settle=()=>new Promise(resolve=>setTimeout(resolve,30));
listeners.updated(1,{status:'complete'},tab);await settle();
assert.equal((await chrome.storage.session.get('tab-1'))['tab-1'].availability,'native');
assert.equal(offers,0);
tab={...tab,url:'https://www.canva.com/'};
listeners.updated(1,{url:tab.url},tab);listeners.updated(1,{status:'complete'},tab);await settle();
assert.equal(offers,1,'simultaneous content/navigation must not duplicate notifications');
const reply=await new Promise(resolve=>listeners.message({action:'offer',url:tab.url},{tab,frameId:0,url:tab.url},resolve));
assert.match(reply.error,/indisponível/,'a content script must not invoke native installation');
await chrome.storage.local.set({enabled:false});await chrome.storage.session.clear();
listeners.updated(1,{status:'complete'},tab);await settle();
assert.deepEqual(await chrome.storage.session.get(null),{});
console.log('PASS: redirecionamento SPA, oferta única, bloqueio de ação nativa da página e detecção desativada.');
