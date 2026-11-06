import fs from 'node:fs';
const source=new URL('../../../packages/linuxbr-system/files/usr/share/linuxbr/store/catalog.json',import.meta.url);
const catalog=JSON.parse(fs.readFileSync(source,'utf8'));
const value={reviewed:catalog.reviewed,apps:catalog.apps.map(({id,name,kind,category,description,source,note})=>({id,name,kind,category,description,source,note}))};
fs.writeFileSync(new URL('../public/applications.json',import.meta.url),JSON.stringify(value,null,2)+'\n');
console.log('Catálogo público preparado: '+value.apps.length+' programas.');
