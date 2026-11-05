// Browser event regressions: an SPA may replace a document before metadata arrives.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const root=new URL('../packages/linuxbr-system/files/usr/share/linuxbr/webapps/',import.meta.url);
const catalog=JSON.parse(fs.readFileSync(new URL('catalog.json',root)));
const listeners={};const event=name=>({addListener:callback=>{listeners[name]=callback;}});
const memory=()=>{const state={};return {
  async get(keys){return keys===null?{...state}:Object.fromEntries((Array.isArray(keys)?keys:[keys]).filter(k=>k in state).map(k=>[k,state[k]]));},
  async set(data){Object.assign(state,data);},async remove(keys){for(const key of Array.isArray(keys)?keys:[keys])delete state[key];},async clear(){for(const key of Object.keys(state))delete state[key];}
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
await chrome.storage.session.set({'settings-startup-reload-7':true,'unrelated-state':'preserved','tab-helper':'preserved',
  'offer-external':'preserved','offer-12345678-1234-4123-8123-123456789abc':{origin:'https://example.org'}});
const toggle=enabled=>new Promise(resolve=>listeners.message({action:'toggle',enabled},{url:chrome.runtime.getURL('popup.html')},resolve));
assert.equal((await toggle(false)).ok,true);
assert.deepEqual(await chrome.storage.session.get(null),{'settings-startup-reload-7':true,'unrelated-state':'preserved','tab-helper':'preserved','offer-external':'preserved'},
  'disabling suggestions must preserve settings recovery markers and unrelated session keys');
assert.equal((await toggle(true)).ok,true);assert.equal((await chrome.storage.session.get('settings-startup-reload-7'))['settings-startup-reload-7'],true);
await chrome.storage.local.set({enabled:false});await chrome.storage.session.clear();
listeners.updated(1,{status:'complete'},tab);await settle();
assert.deepEqual(await chrome.storage.session.get(null),{});
console.log('PASS: redirecionamento SPA, oferta única, bloqueio de ação nativa da página e detecção desativada.');

// Startup recovery must touch only this extension page, once per browser tab.
const manifest=JSON.parse(fs.readFileSync(new URL('manifest.json',root),'utf8'));
const startupEntry=fs.readFileSync(new URL(manifest.background.service_worker,root),'utf8');
const startupImport=startupEntry.match(/import '\.\/(profiles-worker\.js\?revision=[0-9.]+)';/);
assert.ok(startupImport);
const startupSource=fs.readFileSync(new URL(startupImport[1],root),'utf8').replace(/import '\.\/background\.js\?profiles=[0-9.]+';/,'');
const settingsPage='chrome-extension://lhanpdfpjlicodjfidgojclnppokanbi/settings.html';
const startupStorage=chrome.storage.session,reloads=[];
const openTabs=new Map([
  [101,{id:101,status:'complete',url:settingsPage+'?section=downloads&origin=https%3A%2F%2Fexample.org'}],
  [102,{id:102,status:'complete',url:'chrome-extension://another-extension/settings.html'}],
  [103,{id:103,status:'complete',url:settingsPage.replace('settings.html','popup.html')}],
  [104,{id:104,status:'complete',url:'chrome://settings/downloads'}],
  [105,{id:105,status:'complete',url:'https://example.org/settings.html'}],
  [106,{id:106,status:'complete',url:settingsPage+'.other'}],
  [107,{id:107,status:'loading',url:settingsPage+'?section=camera&origin=https%3A%2F%2Fexample.org'}],
  [108,{id:108,status:'complete',url:'chrome-error://chromewebdata/',pendingUrl:settingsPage+'?section=site&origin=https%3A%2F%2Fexample.org'}]
]);
let startupListeners;
function startWorker() {
  const registered={};
  const listen=name=>({addListener:callback=>{registered[name]=callback;}});
  const browser={runtime:{getURL:file=>'chrome-extension://lhanpdfpjlicodjfidgojclnppokanbi/'+file,
      onStartup:listen('startup'),onInstalled:listen('installed')},storage:{session:startupStorage},
    tabs:{onUpdated:listen('updated'),onRemoved:listen('removed'),
      async query(){return [...openTabs.values()].map(value=>({...value}));},
      async get(id){if(!openTabs.has(id))throw new Error('Aba fechada.');return {...openTabs.get(id)};},
      async reload(id){reloads.push(id);registered.updated(id,{status:'complete'},{...openTabs.get(id)});}}};
  vm.runInNewContext(startupSource,{chrome:browser,URL,Set,Promise},{timeout:1000});
  startupListeners=registered;
}
startWorker();startupListeners.startup();startupListeners.installed();
startupListeners.updated(101,{status:'complete'},openTabs.get(101));await settle();
assert.deepEqual(reloads.sort(),[101,108],'simultaneous startup events must recover each matching tab only once');
assert.deepEqual(await startupStorage.get(null),{'settings-startup-reload-101':true,'settings-startup-reload-108':true});
assert.equal((await toggle(false)).ok,true);assert.equal((await toggle(true)).ok,true);
startWorker();startupListeners.startup();startupListeners.installed();await settle();
assert.equal(reloads.length,2,'suggestion off/on and a worker restart must preserve the once-per-tab bound');
openTabs.get(107).status='complete';startupListeners.updated(107,{status:'complete'},openTabs.get(107));await settle();
assert.equal(reloads.filter(id=>id===107).length,1,'a page still loading must wait for completion');
openTabs.set(109,{id:109,status:'complete',url:settingsPage+'?section=invalid'});
startupListeners.updated(109,{status:'complete'},openTabs.get(109));await settle();
assert.equal(reloads.filter(id=>id===109).length,1);
startWorker();await settle();assert.equal(reloads.filter(id=>id===109).length,1,'an invalid request must not loop after worker restart');
startupListeners.removed(101);openTabs.delete(101);await settle();
assert.equal((await startupStorage.get('settings-startup-reload-101'))['settings-startup-reload-101'],undefined);
startupListeners.updated(101,{status:'complete'},{id:101,status:'complete',url:settingsPage});await settle();
assert.equal(reloads.filter(id=>id===101).length,1,'closing a tab before verification must not reload another tab');
console.log('PASS: recuperação da página própria na inicialização, eventos simultâneos, sessão preservada entre workers e nenhuma repetição por aba.');
