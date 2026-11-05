import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';

const directory=new URL('../packages/linuxbr-system/files/usr/share/linuxbr/webapps/',import.meta.url);
const script=fs.readFileSync(new URL('settings.js',directory),'utf8');
const manifest=JSON.parse(fs.readFileSync(new URL('manifest.json',directory)));
const digest=crypto.createHash('sha256').update(Buffer.from(manifest.key,'base64')).digest('hex').slice(0,32);
const identifier=[...digest].map(character=>String.fromCharCode(97+parseInt(character,16))).join('');
assert.equal(identifier,'lhanpdfpjlicodjfidgojclnppokanbi');
assert.deepEqual(manifest.permissions,['storage','tabs','nativeMessaging','notifications']);
assert.equal(manifest.version,'0.8.0.1');
assert.match(manifest.background.service_worker,/^[a-z0-9-]+\.js$/);
assert.notEqual(manifest.background.service_worker,'profiles-worker.js');
const entry=fs.readFileSync(new URL(manifest.background.service_worker,directory),'utf8');
assert.ok(entry.includes("import './profiles-worker.js?revision="+manifest.version+"';"));
const startup=fs.readFileSync(new URL('profiles-worker.js',directory),'utf8');
assert.ok(startup.includes("import './background.js?profiles="+manifest.version+"';"));
const page='chrome-extension://'+identifier+'/settings.html';
let assertions=7;

async function request(query,options={}) {
  const calls=[],status={textContent:'',attributes:{},setAttribute(key,value){this.attributes[key]=value;},focus(){this.focused=true;}},help={hidden:true};
  const context=vm.createContext({URL,location:{href:page+query},
    document:{getElementById:id=>({status,help})[id]},
    chrome:{tabs:{async getCurrent(){if(options.currentError)throw new Error('Falha ao consultar a janela.');return options.noTab?undefined:{id:42};},
      async update(id,data){calls.push({id,...data});if(options.updateError)throw new Error('Falha ao abrir a página.');}}}});
  await vm.runInContext(script,context,{timeout:1000});
  return {calls,status,help};
}

const targets={downloads:'chrome://settings/downloads',notifications:'chrome://settings/content/notifications',
  camera:'chrome://settings/content/camera',microphone:'chrome://settings/content/microphone',
  site:'chrome://settings/content/siteDetails?site=https%3A%2F%2Fexample.org'};
for(const [section,target]of Object.entries(targets)) {
  const result=await request('?section='+section+'&origin=https%3A%2F%2Fexample.org');
  assert.deepEqual(result.calls,[{id:42,url:target}]);assert.equal(result.help.hidden,true);assertions+=2;
}
const idna=await request('?section=site&origin='+encodeURIComponent('https://xn--exemplo-2ya.org'));
assert.equal(idna.calls[0].url,'chrome://settings/content/siteDetails?site=https%3A%2F%2Fxn--exemplo-2ya.org');assertions++;
const invalidQueries=['','?section=downloads','?origin=https%3A%2F%2Fexample.org','?section=unknown&origin=https%3A%2F%2Fexample.org',
  '?section=__proto__&origin=https%3A%2F%2Fexample.org','?section=constructor&origin=https%3A%2F%2Fexample.org',
  '?section=downloads&section=site&origin=https%3A%2F%2Fexample.org','?section=downloads&origin=https%3A%2F%2Fexample.org&origin=https%3A%2F%2Fother.org',
  '?section=downloads&origin=https%3A%2F%2Fexample.org&url=chrome%3A%2F%2Fflags','?section=downloads&origin=https%3A%2F%2Fexample.org#extra'];
for(const origin of ['http://example.org','javascript:alert(1)','file:///tmp/file','https://user:password@example.org',
  'https://example.org/','https://example.org/path','https://example.org?query=1','https://example.org#part',
  'https://EXAMPLE.org','https://example.org:443','https://example.org:8443','https://127.0.0.1','https://2130706433',
  'https://[::1]','https://localhost','https://app.localhost','https://app.local','https://app.internal','https://app.test','https://app.invalid',
  'https://-app.example.org','https://app-.example.org','https://a..example.org','https://example.org\\path','https://example.org\n'])
  invalidQueries.push('?section=site&origin='+encodeURIComponent(origin));
for(const query of invalidQueries) {
  const result=await request(query);
  assert.equal(result.calls.length,0,query);assert.equal(result.status.attributes.role,'alert');
  assert.equal(result.status.focused,true);assert.equal(result.help.hidden,false);assert.match(result.status.textContent,/Não foi possível abrir/);assertions+=5;
}
for(const options of [{noTab:true},{currentError:true},{updateError:true}]) {
  const result=await request('?section=downloads&origin=https%3A%2F%2Fexample.org',options);
  assert.equal(result.status.attributes.role,'alert');assert.equal(result.status.focused,true);assert.equal(result.help.hidden,false);assertions+=3;
}
const html=fs.readFileSync(new URL('settings.html',directory),'utf8');
assert.match(html,/<html lang="pt-BR">/);assert.match(html,/role="status" tabindex="-1"/);assert.match(html,/<script src="settings.js"><\/script>/);assertions+=3;
console.log('PASS: 5 seções nativas, '+invalidQueries.length+' solicitações inválidas, identidade da extensão e falhas acessíveis; '+assertions+' verificações.');
