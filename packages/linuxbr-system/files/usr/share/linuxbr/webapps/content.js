// Only manifest metadata is inspected. No forms, cookies or page text are read.
let scanning=false,rescan=false;
async function inspect() {
  if(scanning){rescan=true;return;}
  scanning=true;
  try {
  if (window !== window.top || location.protocol !== 'https:') return;
  const preferences = await chrome.storage.local.get('enabled');
  if (preferences.enabled === false) return;
  let manifest = null;
  const link = document.querySelector('link[rel~="manifest"]');
  if (link) {
    try {
      const url = new URL(link.getAttribute('href'), location.href);
      if (url.origin === location.origin) {
        const response = await fetch(url, {credentials:'omit', redirect:'error', signal:AbortSignal.timeout(3000)});
        if (response.ok && Number(response.headers.get('content-length') || 0) <= 65536) {
          const reader = response.body.getReader(); let size = 0; const chunks = [];
          for (;;) {
            const {done,value} = await reader.read(); if (done) break;
            size += value.length;
            if (size > 65536) {await reader.cancel(); throw new Error('manifest too large');}
            chunks.push(value);
          }
          const bytes = new Uint8Array(size);let offset=0;
          for (const chunk of chunks) {bytes.set(chunk,offset);offset+=chunk.length;}
          const data=JSON.parse(new TextDecoder().decode(bytes));
          manifest={name:data.short_name || data.name, display:data.display,
            start_url:new URL(data.start_url || '/',url).href};
        }
      }
    } catch { /* A normal site or an unavailable manifest is not an error dialog. */ }
  }
  await chrome.runtime.sendMessage({action:'metadata',manifest}).catch(()=>{});
  } finally {scanning=false;if(rescan){rescan=false;queueMicrotask(()=>inspect().catch(()=>{}));}}
}
inspect().catch(()=>{});
chrome.runtime.onMessage.addListener(message=>{if(message.action==='inspect')inspect().catch(()=>{});});

// Available only in a Linux BR webapp profile, including its login redirects.
async function profileControls() {
  if(window!==window.top || location.protocol!=='https:')return;
  const context=await chrome.runtime.sendMessage({action:'profile-context'});
  if(!context?.available)return;
  const host=document.createElement('div');host.id='linuxbr-profile-controls';
  host.style.cssText='position:fixed!important;right:12px!important;bottom:12px!important;z-index:2147483647!important;';
  const shadow=host.attachShadow({mode:'closed'});
  const style=document.createElement('style');
  style.textContent='div{display:flex;align-items:center;gap:10px;background:#fff;color:#252a31;border:1px solid #c9cbd2;border-radius:10px;padding:8px 10px;box-shadow:0 2px 12px #0003;font:14px system-ui}span{max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}button{background:#6450a2;color:white;border:0;border-radius:6px;padding:8px 12px;font:inherit;cursor:pointer}button:focus-visible{outline:3px solid #17123c}';
  const row=document.createElement('div');
  const label=document.createElement('span');label.textContent=context.session;label.title=context.name+' — '+context.session+'. Arraste para mover.';label.style.cursor='move';
  let drag=null;
  label.addEventListener('pointerdown',event=>{
    if(!event.isTrusted || event.button!==0)return;
    const rect=host.getBoundingClientRect();drag={x:event.clientX-rect.left,y:event.clientY-rect.top};
    label.setPointerCapture(event.pointerId);event.preventDefault();
  });
  label.addEventListener('pointermove',event=>{
    if(!drag)return;
    host.style.right='auto';host.style.bottom='auto';
    host.style.left=Math.max(0,Math.min(innerWidth-host.offsetWidth,event.clientX-drag.x))+'px';
    host.style.top=Math.max(0,Math.min(innerHeight-host.offsetHeight,event.clientY-drag.y))+'px';
  });
  label.addEventListener('pointerup',()=>{drag=null;});label.addEventListener('pointercancel',()=>{drag=null;});
  const button=document.createElement('button');button.textContent='+ Novo perfil';
  button.addEventListener('click',async event=>{
    if(!event.isTrusted)return;
    button.disabled=true;
    try {
      const result=await chrome.runtime.sendMessage({action:'new-profile'});
      if(!result?.opened)button.textContent='Tentar novamente';
    } catch {button.textContent='Tentar novamente';}
    finally {button.disabled=false;}
  });
  row.append(label,button);shadow.append(style,row);document.documentElement.append(host);
}
profileControls().catch(()=>{});
