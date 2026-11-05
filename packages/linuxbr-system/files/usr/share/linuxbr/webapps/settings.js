function profileSettingsTarget(address) {
  const request=new URL(address),parameters=request.searchParams;
  if(request.hash||[...parameters.keys()].some(key=>!['section','origin'].includes(key))||
     parameters.getAll('section').length!==1||parameters.getAll('origin').length!==1)
    throw new Error('Parâmetros de preferências inválidos.');
  const value=parameters.get('origin'),origin=new URL(value),host=origin.hostname;
  if(origin.protocol!=='https:'||origin.username||origin.password||origin.port||
     origin.pathname!=='/'||origin.search||origin.hash||value!==origin.origin||
     !/^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(host)||!host.includes('.')||
     /^\d+\.\d+\.\d+\.\d+$/.test(host)||
     host.split('.').some(label=>!label||label.length>63||label.startsWith('-')||label.endsWith('-'))||
     ['.localhost','.local','.internal','.test','.invalid'].some(suffix=>host.endsWith(suffix)))
    throw new Error('Origem do aplicativo inválida.');
  const pages={downloads:'chrome://settings/downloads',
    site:'chrome://settings/content/siteDetails?site='+encodeURIComponent(origin.origin),
    notifications:'chrome://settings/content/notifications',
    camera:'chrome://settings/content/camera',microphone:'chrome://settings/content/microphone'};
  const section=parameters.get('section');
  if(!Object.hasOwn(pages,section))throw new Error('Preferência de navegador inválida.');
  return pages[section];
}

(async()=>{
  try {
    const target=profileSettingsTarget(location.href),tab=await chrome.tabs.getCurrent();
    if(!tab||!Number.isInteger(tab.id))throw new Error('Janela do perfil indisponível.');
    await chrome.tabs.update(tab.id,{url:target});
  } catch(error) {
    const status=document.getElementById('status');
    status.setAttribute('role','alert');
    status.textContent='Não foi possível abrir estas preferências. '+error.message;
    document.getElementById('help').hidden=false;
    status.focus();
  }
})();
