const box=document.querySelector('#releases');
try{
  const response=await fetch('https://api.github.com/repos/victoremerick/linuxbr/releases?per_page=6',{headers:{Accept:'application/vnd.github+json'}});
  if(!response.ok)throw Error('release-query');
  const releases=await response.json();
  if(!Array.isArray(releases))throw Error('release-format');
  box.replaceChildren();
  const visible=releases.filter(r=>!r.draft&&typeof r.html_url==='string'&&r.html_url.startsWith('https://github.com/victoremerick/linuxbr/releases/tag/')).slice(0,3);
  if(!visible.length){const p=document.createElement('p');p.textContent='As próximas versões serão publicadas no GitHub Releases. Acompanhe o projeto para saber quando um download estiver disponível.';box.append(p);}
  for(const release of visible){
    const card=document.createElement('article');card.className='release-card';
    const content=document.createElement('div');const title=document.createElement('h3');title.textContent=release.name||release.tag_name;
    const info=document.createElement('p');const date=new Date(release.published_at);
    info.textContent=(release.prerelease?'Versão de avaliação':'Versão estável')+(Number.isNaN(date.valueOf())?'':' · '+date.toLocaleDateString('pt-BR'));
    const link=document.createElement('a');link.href=release.html_url;link.textContent='Downloads e notas ↗';
    content.append(title,info);card.append(content,link);box.append(card);
  }
}catch{box.textContent='Não foi possível consultar as versões agora. Acesse o GitHub Releases pelo botão abaixo.';}
