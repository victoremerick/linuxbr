// A new worker URL refreshes previously registered workers in saved profiles.
import './background.js?profiles=0.8.0.1';

// A launch URL can arrive before the extension becomes available at startup.
const settingsPage=new URL(chrome.runtime.getURL('settings.html'));
const settingsReloadPending=new Set();
const settingsReloadKey=id=>'settings-startup-reload-'+id;
function ownSettingsPage(value) {
  try {
    const address=new URL(value);
    return address.protocol===settingsPage.protocol&&address.host===settingsPage.host&&
      address.pathname===settingsPage.pathname&&!address.username&&!address.password;
  } catch {return false;}
}
async function recoverStartupSettings(tab) {
  if(!Number.isInteger(tab.id)||tab.status==='loading'||settingsReloadPending.has(tab.id)||
     ![tab.url,tab.pendingUrl].some(ownSettingsPage))return;
  settingsReloadPending.add(tab.id);
  try {
    const key=settingsReloadKey(tab.id),state=await chrome.storage.session.get(key);
    if(state[key]===true)return;
    const current=await chrome.tabs.get(tab.id);
    if(current.status==='loading'||![current.url,current.pendingUrl].some(ownSettingsPage))return;
    // The session marker survives worker restarts and bounds recovery per tab.
    await chrome.storage.session.set({[key]:true});
    await chrome.tabs.reload(tab.id);
  } catch {} finally {settingsReloadPending.delete(tab.id);}
}
async function recoverOpenSettings() {
  try {await Promise.allSettled((await chrome.tabs.query({})).map(recoverStartupSettings));}
  catch {}
}
chrome.runtime.onStartup.addListener(recoverOpenSettings);
chrome.runtime.onInstalled.addListener(recoverOpenSettings);
chrome.tabs.onUpdated.addListener((id,change,tab)=>{
  if(change.status==='complete')recoverStartupSettings({...tab,id});
});
chrome.tabs.onRemoved.addListener(id=>chrome.storage.session.remove(settingsReloadKey(id)).catch(()=>{}));
recoverOpenSettings();
