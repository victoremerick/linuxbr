# Manutenção do repositório local — 0.8

`scripts/repository-maintenance.py` confere uma publicação APT local e os arquivos TLS existentes. Também renova somente o certificado de servidor, preservando a autoridade certificadora, a chave privada do servidor e a confiança já instalada nos clientes. Nenhum comando inicia, reinicia ou configura serviços.

Requisitos no servidor: Python 3, OpenSSL 3 e `gpgv`. A geração de índices continua em `scripts/build-repository.py`, com GnuPG e os requisitos já documentados para a publicação. Arquivos privados permanecem fora do diretório público.

## Conferir a publicação e o TLS

```sh
python3 scripts/repository-maintenance.py health \
  --publication "$HOME/.local/share/linuxbr/repositorio-atual" \
  --tls-dir "$HOME/.local/state/linuxbr-repositorio/tls" \
  --keyring /caminho/confiavel/linuxbr-archive-keyring.gpg \
  --hostname atualizacoes.lan
```

Use o nome ou IP que os clientes realmente utilizam. O resultado JSON inclui estado, horário, datas, impressões digitais e os componentes conferidos. Códigos de saída: `0` para conferência sem alertas, `1` para alerta e `2` para erro. `--warn-days` ajusta a antecedência do aviso, com padrão de três dias.

São conferidos:

- assinaturas disponíveis de `InRelease` e `Release.gpg` por `gpgv`, em diretório de trabalho temporário;
- igualdade do conteúdo assinado em `InRelease` com `Release`, quando ambos estão presentes;
- campos `Date` e `Valid-Until`, inclusive expiração, intervalo incoerente e data futura além da tolerância de cinco minutos;
- tamanho e SHA256 de cada índice relacionado na seção assinada `SHA256`;
- cadeia TLS, finalidade de servidor, nome/IP solicitado, datas do servidor e da CA, e correspondência entre certificado e chave privada;
- arquivos ausentes, links em caminhos de índices e permissões abertas na chave privada do servidor.

Uma assinatura expirada, revogada, inválida ou sem chave verificável é recusada. `health` não assina arquivos nem usa uma chave privada GPG. A conferência dos índices não substitui a validação do conteúdo dos pacotes pelo APT.

O argumento `--keyring` é opcional. Sem ele, usa-se `linuxbr-archive-keyring.gpg` da própria publicação e emite-se um alerta: isso confirma a consistência da assinatura com aquele arquivo, mas não estabelece a identidade do publicador por uma referência independente. A impressão digital deve ser comparada com a já conhecida. Sem `--hostname`, a ausência da conferência do nome também aparece como alerta.

O estado é uma observação dos arquivos locais. A disponibilidade da rede, o certificado efetivamente carregado pelo processo servidor e o acesso de um cliente ainda precisam ser conferidos na conexão real.

## Renovar o certificado de servidor

O diretório TLS deve conter `ca.crt`, `ca.key`, `server.crt` e `server.key` regulares, sem links. As duas chaves privadas precisam de permissão `0600`. O fluxo atual aceita chaves locais sem senha; não altera senhas nem remove proteção de uma chave criptografada.

```sh
python3 scripts/repository-maintenance.py renew-certificate \
  --tls-dir "$HOME/.local/state/linuxbr-repositorio/tls" \
  --hostname atualizacoes.lan \
  --days 397
```

O comando também aceita `--renew-certificate` no lugar de `renew-certificate`. O nome é obrigatório e precisa ser aceito pelo certificado existente. Não é acrescentado um nome novo silenciosamente. Todos os SAN existentes são copiados pelo OpenSSL e conferidos antes da troca, incluindo DNS e endereços IP.

Somente o certificado de servidor é reemitido, com um novo número de série e a mesma chave pública. `ca.crt`, `ca.key` e `server.key` permanecem com os mesmos conteúdos. A chave GPG não participa dessa operação. A CA precisa estar válida e cobrir todo o prazo solicitado; caso contrário, a ferramenta recusa a operação. É possível reduzir `--days`, de 1 a 397. A renovação da própria autoridade e a redistribuição de confiança são um procedimento separado.

Antes de substituir `server.crt`, a ferramenta valida cadeia, finalidade, nome, SAN e chave do novo certificado. O anterior é salvo como `server.crt.previous-DATA-IDENTIFICADOR.pem`. O arquivo novo é preparado no mesmo sistema de arquivos e substituído atomicamente. Uma trava impede duas renovações simultâneas. Uma falha anterior à substituição conserva o certificado em uso. Não são criados arquivos de série da CA nem substituídas suas chaves.

A saída informa o backup e a nova validade, com `service_reloaded: false`. Use o procedimento de operação do servidor para recarregá-lo. O servidor PHP iniciado em terminal deve ser encerrado e iniciado novamente com os mesmos caminhos TLS e a publicação revisada. A conexão em andamento pode continuar com o certificado que já estava carregado.

Depois da recarga, confirme a conexão com a CA já conhecida:

```sh
openssl s_client -connect atualizacoes.lan:8443 \
  -servername atualizacoes.lan \
  -CAfile "$HOME/.local/state/linuxbr-repositorio/tls/ca.crt" \
  -verify_return_error -verify_hostname atualizacoes.lan </dev/null
```

Repita a conferência a partir de um cliente e consulte o repositório pelo APT configurado. A renovação sob a mesma CA não exige instalar outra CA, mudar `Signed-By`, trocar keyring ou desativar verificações TLS no cliente.

## Nova publicação dos índices

Os índices expiram independentemente do certificado TLS. Use uma pasta de saída nova e a impressão digital completa da chave de assinatura explicitamente escolhida:

```sh
python3 scripts/build-repository.py \
  --packages dist/packages \
  --output "$HOME/.local/share/linuxbr/repositorio-novo" \
  --fingerprint IMPRESSAO_DIGITAL_COMPLETA_DA_CHAVE \
  --base-url https://atualizacoes.lan:8443
```

Revise a publicação resultante e execute `health` antes da troca. Os arquivos públicos específicos do servidor local, como os exemplos `client.*`, permanecem sob o fluxo de preparo existente; não copie chaves privadas para a publicação. Para preparar novamente esse conjunto completo com a mesma identidade TLS válida, use `setup-local-repository.py --reuse-tls` em uma saída nova. Essa opção reutiliza os arquivos TLS; a renovação da validade é feita pelo comando acima.

Preserve a publicação anterior. Interrompa o atendimento durante a troca do diretório público e retome-o apontando para a saída escolhida, conforme o fluxo já documentado. Nenhuma publicação é assinada automaticamente pelo comando de saúde ou de renovação.

## Retorno após falha

Se a renovação for recusada, leia a mensagem antes de repetir. Nome incorreto, CA próxima de vencer, chave divergente, link e permissões inadequadas precisam ser corrigidos explicitamente. Uma trava remanescente só deve ser removida depois de conferir que não há outra operação em andamento.

Se o processo servidor não carregar o novo certificado, confirme seus caminhos e permissões e consulte o registro do próprio processo. O backup anterior permite restaurar o certificado que estava funcionando, desde que ainda esteja válido e corresponda ao mesmo nome e chave. Não use um certificado expirado nem desative verificação de validade para voltar a atender clientes.

Exemplo de restauração manual em Bash, depois de interromper o servidor e escolher o arquivo de backup correto:

```sh
set -e
TLS_DIR="$HOME/.local/state/linuxbr-repositorio/tls"
CERT_BACKUP="$TLS_DIR/server.crt.previous-DATA-IDENTIFICADOR.pem"
openssl verify -CAfile "$TLS_DIR/ca.crt" -purpose sslserver \
  -verify_hostname atualizacoes.lan "$CERT_BACKUP"
cmp <(openssl x509 -in "$CERT_BACKUP" -pubkey -noout) \
    <(openssl pkey -in "$TLS_DIR/server.key" -pubout)
cp -- "$TLS_DIR/server.crt" "$TLS_DIR/server.crt.before-rollback.pem"
CERT_STAGE=$(mktemp "$TLS_DIR/.restore-XXXXXX")
install -m 644 "$CERT_BACKUP" "$CERT_STAGE"
mv -fT -- "$CERT_STAGE" "$TLS_DIR/server.crt"
```

Execute `health`, reinicie o processo pelo procedimento normal e confira novamente uma conexão real. A publicação anterior pode ser retomada pelo mesmo fluxo de troca de diretório, desde que seus metadados ainda estejam válidos; se expiraram, gere índices novos e assinados a partir dos pacotes revisados. Os backups não tornam válidos certificados ou índices já expirados.

## Validação

`python3 tests/test-repository-maintenance-08.py -v` executou sete testes reais em laboratório, usando somente diretórios temporários: assinaturas GPG, hash/tamanho de índice, datas inválidas, adulterações, preservação de CA/chaves/SAN, backup do certificado anterior, recusa de nome ou chave incorretos, permissões, links e trava concorrente. A renovação foi seguida de uma conexão TLS em loopback validada com a CA original.

Nenhum serviço ou arquivo de confiança da sessão de trabalho foi alterado. A troca da publicação e a recarga do servidor de produção dependem de operação explícita sobre o ambiente escolhido.

Referências: [opções do OpenSSL x509](https://docs.openssl.org/3.3/man1/openssl-x509/), [formato do repositório Debian](https://wiki.debian.org/DebianRepository/Format) e [configuração de confiança das fontes APT](https://manpages.debian.org/trixie/apt/sources.list.5.en.html).
