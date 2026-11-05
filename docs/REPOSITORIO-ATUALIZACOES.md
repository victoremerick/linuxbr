# Repositório de atualizações Linux BR

## Preparação

Use GnuPG e dpkg-dev em uma máquina Linux. Mantenha GNUPGHOME e os backups da chave privada fora do projeto e da pasta publicada. Guarde uma cópia protegida da chave e do certificado de revogação. O teste automatizado cria uma chave temporária de um dia, descartada ao terminar; essa chave não serve para produção.

Crie uma chave de assinatura com `gpg --full-generate-key`, confira a impressão digital completa e execute:

```sh
python3 scripts/build-repository.py \
  --packages dist/packages \
  --output dist/repository-0.6-beta1 \
  --fingerprint IMPRESSAO_DIGITAL_COMPLETA \
  --base-url https://SEU_DOMINIO/linuxbr
```

O endereço é um exemplo a substituir. Sem --base-url, o repositório é preparado localmente sem arquivo de fonte para clientes. O script não cria serviço de rede nem publica arquivos na internet.

## Publicação e clientes

Publique somente a pasta de saída em HTTPS. Mantenha os arquivos do pool das versões anteriores durante o período de atualização dos clientes. Faça a troca da árvore dists de forma atômica para não expor índices incompletos. Renove a assinatura antes dos 14 dias de validade, mesmo quando não houver pacotes novos.

Confira a impressão digital por um canal confiável antes de instalar a chave pública. Instale linuxbr-archive-keyring.gpg em /usr/share/keyrings/, linuxbr.sources em /etc/apt/sources.list.d/ e linuxbr.pref em /etc/apt/preferences.d/. Use autorização administrativa do sistema. Depois, atualize os índices e revise as versões no Discover. A chave é vinculada somente a essa fonte por Signed-By; não use trusted=yes nem desative verificações de assinatura ou validade.

Os pacotes antigos não são removidos automaticamente. O Dolphin customizado exige a versão correspondente de seus componentes; publique o conjunto completo produzido pelo build. Antes de liberar, teste uma atualização da instalação anterior e o login após reiniciar, mantendo uma cópia recuperável dos arquivos pessoais.

## Evidências automatizadas

`python3 tests/repository-integration.py CAMINHO_DOS_DEBS` cria um repositório temporário, verifica InRelease com gpgv, executa apt-get update com fontes, listas e cache isolados e confirma a rejeição de índices modificados. Não altera /etc/apt nem as fontes do computador.

Referências: [formato Debian](https://wiki.debian.org/DebianRepository/Format) e [vinculação de chaves de terceiros](https://wiki.debian.org/DebianRepository/UseThirdParty).
