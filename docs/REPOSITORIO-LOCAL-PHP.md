# Atualizações locais por HTTPS com PHP

Esta opção publica os pacotes revisados em um computador da rede local. O servidor usa PHP CLI com OpenSSL, sem servidor web adicional, banco de dados ou dependências PHP externas. A assinatura APT continua sendo produzida pelo GnuPG. O preparo não inicia um serviço nem altera as fontes APT de nenhum cliente.

## Preparar o servidor

Use Linux com Python 3, PHP CLI com extensão OpenSSL, `openssl`, `gnupg`, `dpkg-dev` e acesso à chave de assinatura já configurada no GnuPG. O PHP precisa oferecer TLS 1.2/1.3. No Debian 13 essas capacidades estão disponíveis nos pacotes usuais. Os pacotes DEB devem ser os arquivos revisados da versão que será distribuída.

Mantenha a chave GPG fora da pasta pública. Informe sua impressão digital completa; a ferramenta não gera uma chave de assinatura de produção, não remove sua senha nem copia material privado para a publicação.

Para preparar uma publicação acessível apenas neste computador:

```sh
python3 scripts/setup-local-repository.py \
  --packages dist/packages \
  --output "$HOME/.local/share/linuxbr/repositorio-0.7" \
  --tls-dir "$HOME/.local/state/linuxbr-repositorio/tls" \
  --fingerprint IMPRESSAO_DIGITAL_COMPLETA_DA_CHAVE \
  --hostname localhost --port 8443

php scripts/repository-server.php \
  --root "$HOME/.local/share/linuxbr/repositorio-0.7" \
  --cert "$HOME/.local/state/linuxbr-repositorio/tls/server.crt" \
  --key "$HOME/.local/state/linuxbr-repositorio/tls/server.key" \
  --port 8443
```

O servidor permanece no terminal e pode ser interrompido com Ctrl+C. Execute-o pela conta proprietária dos arquivos; a porta 8443 dispensa privilégios administrativos. O endereço padrão de escuta é `127.0.0.1`.

O preparo cria uma CA local autoassinada e um certificado de servidor assinado por ela, com SAN para `localhost`, `127.0.0.1` e o nome/IP escolhido. As chaves ficam na pasta TLS privada, com permissão 0600. A chave da CA não precisa ser entregue ao processo servidor; guarde-a para renovações. Apenas o certificado público da CA é copiado para a publicação.

Para outro computador acessar, escolha um nome DNS ou IPv4 que os clientes consigam resolver, informe-o em `--hostname`, e acrescente `--address` para IPs adicionais do certificado. Por exemplo, `--hostname atualizacoes.lan --address 192.168.1.10`. Esses valores são exemplos e precisam corresponder à rede real. Ao iniciar, acrescente `--bind 192.168.1.10 --allow-lan`. A escuta em rede exige essa opção explícita. Libere apenas a porta necessária para os clientes pretendidos na configuração de firewall da rede.

Para máquinas QEMU com rede de usuário padrão, `10.0.2.2` costuma representar o acesso ao computador hospedeiro. Se essa for a configuração efetiva da VM, prepare o certificado com `--hostname 10.0.2.2` e mantenha o servidor no loopback do hospedeiro. Isso não publica o serviço para outros computadores da rede física.

## Configurar um cliente

Transfira os arquivos públicos por um canal já confiável, como mídia local ou SSH autenticado. Confira a impressão digital da chave GPG e os hashes da CA e do keyring com os valores obtidos diretamente no preparo do servidor. Aceitar um certificado desconhecido ou baixar CA/chave sem uma referência confiável não estabelece a confiança inicial.

Revise `client.sources`, `client-https.conf`, `client.pref` e `client-readme.txt`. O nome de servidor desses arquivos precisa ser o mesmo usado no certificado. Depois instale explicitamente os arquivos no cliente:

```sh
sudo install -d -m 755 /etc/apt/certs
sudo install -m 644 linuxbr-local-ca.crt /etc/apt/certs/linuxbr-local-ca.crt
sudo install -m 644 client-archive-keyring.gpg /usr/share/keyrings/linuxbr-local-archive-keyring.gpg
sudo install -m 644 client-https.conf /etc/apt/apt.conf.d/80linuxbr-local-https
sudo install -m 644 client.pref /etc/apt/preferences.d/linuxbr-local
sudo install -m 644 client.sources /etc/apt/sources.list.d/linuxbr-local.sources
sudo apt-get update
```

Os comandos pressupõem que os arquivos transferidos estão na pasta atual. Não execute o conteúdo de um arquivo de configuração como script. Revise se já existe outra fonte Linux BR para o mesmo repositório antes de cadastrar uma duplicata.

`Signed-By` limita a chave aceita para esta fonte. A CA local é configurada somente para o host do repositório, em `Acquire::https::HOST::CaInfo`, dentro do APT; ela não é adicionada ao conjunto global de autoridades do navegador ou de outros aplicativos. `Verify-Peer` e `Verify-Host` permanecem ativados. O servidor não exige certificado de cliente: ele fornece arquivos públicos, cuja autenticidade é verificada pelo cliente com TLS e assinatura APT.

A disposição do nome do host segue a implementação do APT 3.0.3: `ConfigFind` consulta `Acquire::<método>::<host>::<opção>`. Algumas revisões da página de manual apresentam a CA na ordem inversa. A configuração distribuída deve passar pela integração real com `apt-get update`, incluindo a rejeição de uma CA diferente; consultar apenas o texto do arquivo com `apt-config dump` não demonstra que o transporte HTTPS leu a opção.

Após o cadastro, a Central do Sistema e o gerenciador de atualizações podem consultar os pacotes pelo APT existente. Nenhum cliente deve receber chaves privadas TLS/GPG.

## Novas publicações e renovação

Cada publicação tem saída nova. Use `--reuse-tls` com a mesma pasta TLS para conservar a CA e verificar que o certificado e sua chave correspondem ao nome escolhido. Essa opção reutiliza o certificado; não renova sua validade. A partir da 0.8, siga [manutenção do repositório](REPOSITORIO-MANUTENCAO-0.8.md) para renovar apenas o certificado de servidor com a mesma CA, preservando a confiança dos clientes. A substituição da própria CA é um procedimento separado: exige distribuir a nova autoridade por um canal confiável e ajustar os clientes antes da troca.

Os metadados APT gerados por `build-repository.py` expiram em 14 dias. Na 0.9, `repository-maintenance.py renew-metadata` verifica a publicação com uma chave previamente confiável e renova datas e assinaturas quando faltam até três dias. Os índices dos pacotes permanecem iguais; a troca do diretório de metadados é atômica, com reversão se a conferência final falhar. A chave privada de assinatura permanece somente no servidor de publicação. Metadados adulterados, vencidos ou assinados por outra identidade são recusados; uma publicação vencida exige revisão e preparo explícito de uma nova saída.

```sh
GNUPGHOME=/caminho/privado/gnupg python3 scripts/repository-maintenance.py renew-metadata \
  --publication /caminho/publicacao \
  --keyring /caminho/confiavel/archive-keyring.gpg \
  --fingerprint IMPRESSAO_DIGITAL_COMPLETA
```

Agende essa operação diariamente pela conta proprietária da publicação, com o mesmo `GNUPGHOME`. Use um serviço `Type=oneshot` e um timer `OnCalendar=daily`, `Persistent=true`, protegendo os caminhos privados. A operação retorna `unchanged` enquanto a validade estiver distante do limite. `--force` permite uma renovação revisada antes desse limite e serve para validação; não desativa conferências de assinatura ou integridade. O certificado de servidor dura 397 dias e a CA, 1825 dias. Relógios corretos no servidor e nos clientes são necessários para verificar as validades.

Pare o servidor antes de trocar o diretório de publicação e reinicie-o apontando para a saída revisada. Preserve a publicação anterior para recuperação. Não altere os arquivos enquanto o servidor os fornece. O diretório público deve ser gravável somente pelo responsável pela publicação e não pode conter dados pessoais ou chaves.

## Limites e validação

O endpoint aceita somente GET/HEAD para uma lista explícita de índices APT, pacotes DEB, chave pública e arquivos públicos de configuração. Não lista diretórios, não executa PHP da pasta publicada, não recebe uploads e não oferece HTTP sem TLS. Caminhos codificados, travessia de diretórios, links simbólicos e arquivos fora da publicação são recusados. Há limites de tamanho e tempo para cabeçalhos e transferências; conexões são encerradas após cada resposta.

O atendimento é sequencial, adequado a uma rede local pequena. Uma máquina sem resposta pode ocupar brevemente a conexão até o limite de tempo. Para grande volume ou exposição à Internet, será necessária outra infraestrutura de hospedagem, mantendo as assinaturas e verificações dos clientes.

```sh
php -l scripts/repository-server.php
php tests/test-repository-server.php
python3 tests/local-repository-integration.py
```

O teste PHP usa conexões TLS reais no loopback: GET/HEAD, hash de download, métodos indevidos, traversal codificado, PHP não executado, cabeçalhos excessivos, nome/CA TLS incorretos, recusa de LAN sem opção explícita e proteção das chaves. A verificação de symlink exige Linux ou permissão de criar symlinks no Windows; a ausência dessa permissão aparece como teste não executado.

A integração Linux cria chave GPG, pacote, certificados e estado APT temporários; valida atualização e download por HTTPS, rejeição de CA desconhecida, metadados e pacote adulterados, e proteção contra sobrescrever uma publicação. Nenhuma fonte real é ativada por esses testes. Eles exigem permissão de abrir/conectar sockets no loopback.

Referências: [consulta efetiva da configuração do APT 3.0.3](https://github.com/Debian/apt/blob/3.0.3/methods/aptmethod.h), [carregamento da CA pelo transporte TLS](https://github.com/Debian/apt/blob/3.0.3/methods/connect.cc), [formato e Signed-By das fontes APT](https://manpages.debian.org/trixie/apt/sources.list.5.en.html), [sockets de servidor no PHP](https://www.php.net/manual/en/function.stream-socket-server.php) e [contexto SSL/TLS do PHP](https://www.php.net/manual/en/context.ssl.php).
