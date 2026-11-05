import {classify, shouldNotify} from './rules.js';
const HOST='org.linuxbr.webapps';
const catalog=fetch(chrome.runtime.getURL('catalog.json')).then(response=>response.json());
const native=message=>chrome.runtime.sendNativeMessage(HOST,message);
const key=id=>'tab-'+id;
const notifying=new Set();

async function candidateFor(id) {return (await chrome.storage.session.get(key(id)))[key(id)] || null;}
async function decorate(id,item) {
  const text=!item?'':item.installed?'OK':item.availability==='native'||item.native_installed?'Linux':item.availability==='web'?'+':'?';
  await chrome.action.setBadgeBackgroundColor({tabId:id,color:'#6450a2'});
  await chrome.action.setBadgeText({tabId:id,text});
  await chrome.action.setTitle({tabId:id,title:item?`${item.name} — Aplicativos web Linux BR`:'Aplicativos web Linux BR'});
}
async function offerNotification(tab,item) {
  if(notifying.has(item.origin))return;
  notifying.add(item.origin);
  try {
  const prefs=await chrome.storage.local.get(['enabled','ignored','offered']);
  if (!tab.active || !shouldNotify(item,prefs) || !(await chrome.windows.get(tab.windowId)).focused) return;
  const now=Date.now();const offered=Object.fromEntries(Object.entries(prefs.offered || {}).filter(([,date])=>now-date<30*86400000));
  offered[item.origin]=now;await chrome.storage.local.set({offered});
  const id='offer-'+crypto.randomUUID();
  await chrome.storage.session.set({[id]:item});
  await chrome.notifications.create(id,{type:'basic',iconUrl:'icon.png',
    title:`Usar ${item.name} como aplicativo?`,
    message:'Abra em uma janela própria, com atalho no menu do Linux BR.',
    buttons:[{title:'Ver instalação'},{title:'Não sugerir este site'}]});
  } finally {notifying.delete(item.origin);}
}
async function metadata(message,sender) {
  if (!sender.tab || sender.frameId!==0 || sender.tab.incognito) return;
  const prefs=await chrome.storage.local.get(['enabled','ignored']);
  if (prefs.enabled===false) return;
  const item=classify(sender.url,message,await catalog);
  if (!item) return;
  const current=await chrome.tabs.get(sender.tab.id);
  if (current.url!==sender.url) return; // A navigation completed while metadata was fetched.
  try {const result=await native({action:'status',url:item.url,name:item.name});if(result.error)throw new Error(result.error);Object.assign(item,result);}
  catch {item.hostUnavailable=true;}
  if((await chrome.tabs.get(sender.tab.id)).url!==sender.url)return;
  if((await chrome.storage.local.get('enabled')).enabled===false)return;
  await chrome.storage.session.set({[key(sender.tab.id)]:item});
  await decorate(sender.tab.id,item);
  if (!item.hostUnavailable) await offerNotification(current,item);
}
async function popup(message) {
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(message.action==='manage')return native({action:'manage'});
  if(message.action==='state') {
    let item=tab?await candidateFor(tab.id):null;
    if(item)try {Object.assign(item,await native({action:'status',url:item.url,name:item.name}));}catch{item.hostUnavailable=true;}
    return {item,preferences:await chrome.storage.local.get(['enabled','ignored']),incognito:tab?.incognito};
  }
  if(message.action==='toggle') {
    await chrome.storage.local.set({enabled:message.enabled===true});
    if (!message.enabled) {
      for(const open of await chrome.tabs.query({}))await decorate(open.id,null);
      const suggestions=Object.keys(await chrome.storage.session.get(null)).filter(name=>
        /^tab-\d+$/.test(name)||/^offer-[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(name));
      if(suggestions.length)await chrome.storage.session.remove(suggestions);
      for(const id of Object.keys(await chrome.notifications.getAll()))await chrome.notifications.clear(id);
    } else if(tab)await chrome.tabs.sendMessage(tab.id,{action:'inspect'}).catch(()=>{});
    return {ok:true};
  }
  if(message.action==='reset'){await chrome.storage.local.set({ignored:{},offered:{}});return {ok:true};}
  const item=tab?await candidateFor(tab.id):null;
  if(!item || tab.incognito)throw new Error('Recarregue o site para identificar o aplicativo.');
  if(message.action==='offer')return native({action:'offer',url:item.url,name:item.name});
  if(message.action==='ignore') {
    const {ignored={}}=await chrome.storage.local.get('ignored');ignored[item.origin]=true;
    await chrome.storage.local.set({ignored});return {ok:true};
  }
  throw new Error('Ação não reconhecida.');
}
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  // Profile controls only open confirmation UI for the browser's own profile.
  const trustedPopup=sender.url===chrome.runtime.getURL('popup.html');
  const profileAction=sender.tab && sender.frameId===0 && !sender.tab.incognito &&
    ['profile-context','new-profile','profile-preferences','external-link'].includes(message.action);
  const task=profileAction?native({action:message.action,...(message.action==='external-link'?{url:message.url}:{})}):trustedPopup?popup(message):(message.action==='metadata'?metadata(message,sender):Promise.reject(new Error('Ação indisponível.')));
  task.then(value=>respond(value||{})).catch(error=>respond({error:error.message}));return true;
});
chrome.tabs.onRemoved.addListener(id=>chrome.storage.session.remove(key(id)));
chrome.tabs.onUpdated.addListener((id,change,tab)=>{
  if(change.status==='loading') {chrome.storage.session.remove(key(id));decorate(id,null).catch(()=>{});}
  // SPAs may redirect after document_idle; inspect the final document as well.
  if(change.status==='complete'||change.url) {
    chrome.tabs.sendMessage(id,{action:'inspect'}).catch(()=>{});
    // Known services only need their exact domain, even if an SPA replaces its
    // first document before the content script finishes reading its manifest.
    metadata({manifest:null},{tab,frameId:0,url:tab.url}).catch(()=>{});
  }
});
chrome.tabs.onActivated.addListener(async ({tabId})=>{
  try {const item=await candidateFor(tabId);if(item)await offerNotification(await chrome.tabs.get(tabId),item);}catch{}
});
chrome.windows.onFocusChanged.addListener(async windowId=>{
  if(windowId===chrome.windows.WINDOW_ID_NONE)return;
  try {const [tab]=await chrome.tabs.query({active:true,windowId});const item=tab?await candidateFor(tab.id):null;if(item)await offerNotification(tab,item);}catch{}
});
chrome.notifications.onClicked.addListener(async id=>{
  const item=(await chrome.storage.session.get(id))[id];if(!item)return;
  try {await native({action:'offer',url:item.url,name:item.name});}
  finally {await chrome.notifications.clear(id);await chrome.storage.session.remove(id);}
});
chrome.notifications.onButtonClicked.addListener(async (id,index)=>{
  const item=(await chrome.storage.session.get(id))[id];if(!item)return;
  try {
    if(index===0)await native({action:'offer',url:item.url,name:item.name});
    else {const {ignored={}}=await chrome.storage.local.get('ignored');ignored[item.origin]=true;await chrome.storage.local.set({ignored});}
  } finally {await chrome.notifications.clear(id);await chrome.storage.session.remove(id);}
});
chrome.notifications.onClosed.addListener(id=>chrome.storage.session.remove(id));
