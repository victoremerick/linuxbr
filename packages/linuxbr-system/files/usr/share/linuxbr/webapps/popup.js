const get=id=>document.getElementById(id);
const send=message=>chrome.runtime.sendMessage(message);
async function render() {
  const {item,preferences,incognito,error}=await send({action:'state'});
  if(error)throw new Error(error);
  get('install').hidden=true;get('ignore').hidden=true;get('origin').textContent='';
  get('enabled').checked=preferences.enabled!==false;
  let text='Não identificamos um aplicativo web neste site. Você pode adicionar um endereço pelo gerenciador.';
  if(incognito)text='A identificação fica desativada em janelas anônimas.';
  else if(preferences.enabled===false)text='As sugestões estão desativadas. Ative e recarregue o site para identificá-lo.';
  else if(item) {
    text=item.installed?`${item.name} já está instalado no menu do Linux BR.`:
      item.native_installed?`${item.name} já possui um aplicativo instalado neste computador.`:
      item.availability==='native'?`${item.name} oferece aplicativo Linux. Prefira a loja ou o site oficial.`:
      item.availability==='web'?`${item.name}: versão web disponível; o catálogo não identifica aplicativo Linux oficial.`:
      `${item.name} oferece modo aplicativo. A disponibilidade de uma versão Linux não foi confirmada.`;
    get('origin').textContent=new URL(item.url).hostname;
    get('install').hidden=item.installed||item.native_installed||item.availability==='native';
    get('ignore').hidden=Boolean(preferences.ignored?.[item.origin]);
    if(item.hostUnavailable)text+=' Não foi possível conectar ao gerenciador Linux BR.';
  }
  get('status').textContent=text;
}
async function action(message) {
  try {
    const reply=await send(message);if(reply.error)throw new Error(reply.error);
    get('result').textContent=reply.opened?'Confira a janela de confirmação do Linux BR.':'Preferência salva.';
    if(reply.opened){window.close();return;}
    if(message.action!=='offer'&&message.action!=='manage')await render();
  } catch(error) {get('result').textContent='Não foi possível concluir: '+error.message;}
}
for(const id of ['install','ignore','manage','reset'])get(id).onclick=()=>action({action:id==='install'?'offer':id});
get('enabled').onchange=()=>action({action:'toggle',enabled:get('enabled').checked});
render().catch(error=>{get('status').textContent='Não foi possível verificar o site: '+error.message;});
