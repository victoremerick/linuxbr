# Catálogo de aplicativos web Linux BR

Servidor PHP/MySQL com painel Angular. Os perfis, cookies e contas permanecem no computador do usuário. O servidor publica metadados de aplicativos; não distribui nem atualiza o código hospedado pelos fornecedores.

## Requisitos

- PHP 8.2 ou superior com PDO MySQL, Sodium e cURL.
- MySQL 8 ou compatível, banco e usuário próprios para este serviço.
- HTTPS válido, Apache/LiteSpeed com reescrita e tarefa cron.
- Node 22.12 ou superior compatível com Angular 21 apenas para compilar o painel. A hospedagem não precisa executar Node.

## Preparação

Execute `npm ci` e `npm run build` em `admin`. O resultado fica em `public/admin`. Envie `src`, `bin`, `schema.sql` e `private` para um diretório privado; configure a raiz do site para `public`. Não publique o repositório inteiro, arquivos de configuração, chaves, sessões, fontes administrativas ou dependências de compilação.

Copie `config.example.php` para `private/config.php`, preencha o banco exclusivo e a URL HTTPS pública sem barra final. Mantenha a configuração e a chave com modo 0600 e o diretório privado com 0700. Configure `LINUXBR_CATALOG_CONFIG` se a configuração estiver em outro local.

Execute `php bin/setup.php`, fornecendo pela entrada padrão um objeto JSON com `username` e `password`. A senha deve ter pelo menos 14 caracteres. Não inclua a senha na linha de comando ou em arquivos públicos. A ferramenta cria as tabelas, uma chave Ed25519 e o administrador. Não execute novamente para recriar uma instalação existente.

No compartilhado com `public_html` fixo, mantenha a árvore privada fora dele. Um pequeno ponto de entrada PHP dentro do diretório público deve carregar o `public/api.php` privado por caminho absoluto. Copie somente o painel compilado e as regras públicas de reescrita. Ajuste os caminhos das regras ao subdiretório escolhido. Valide que `private/config.php`, `schema.sql`, `src/` e `bin/` não respondem pela internet.

## Operação

- Abra `admin/`, entre e cadastre os aplicativos como rascunho. Use favicon do fornecedor e imagens HTTPS autorizadas.
- Revise URL, categoria, descrição, disponibilidade no Linux, notas da revisão e resultado da verificação. A verificação de disponibilidade não comprova propriedade do domínio ou segurança do aplicativo.
- Salve o estado publicado e use a ação de publicação do catálogo. Cada publicação recebe revisão crescente, emissão e validade de sete dias.
- Execute `php bin/maintain.php` a cada hora pelo cron da hospedagem. Cada chamada verifica até três sites e renova publicações com mais de 24 horas. Não exige processo residente.
- Faça backup do banco, configuração e chave privada em armazenamento protegido. A perda da chave exige revisão explícita de confiança em cada cliente.
- Monitore falhas de cron e expiração. O cliente permite consultar a cópia offline expirada, mas impede aplicar suas alterações.

## Protocolo e confiança

O descritor está em `api.php?action=discovery` e, com reescrita, em `.well-known/linuxbr-webapps`. Contém `schema`, `source_id`, `name`, `catalog_url`, `public_key` Base64 e `fingerprint` SHA-256 da chave pública de 32 bytes. Confira a impressão digital por canal independente antes de adicionar a fonte à Loja.

O catálogo é um envelope com `algorithm=ed25519`, `key_id`, `payload` e `signature` Base64. A assinatura corresponde aos bytes decodificados de `payload`, sem recodificação do JSON. O documento interno contém identidade, revisão, emissão, expiração e aplicativos. Revisões antigas e reutilização de uma revisão com conteúdo diferente são recusadas.

Revisões de nome e metadados podem ser aplicadas mantendo o diretório do perfil. Mudanças na URL exigem revisão e nova instalação separada; os cookies existentes não são transferidos automaticamente. A versão do fornecedor só é informada quando há referência oficial, nunca inferida de uma mudança de HTML.

Para trocar a chave, preserve o banco e a sequência de revisões, gere e proteja uma nova chave e publique uma revisão superior. Divulgue sua impressão digital por canal independente. Na Loja, selecione a fonte e use **Revisar chave do catálogo selecionado**. A substituição é explícita, verifica a identidade da fonte e mantém o limite mínimo de revisão.

## Validação de implantação

Confira HTTPS, descoberta, assinatura, busca, login, CSRF, edição concorrente, publicação, cron e aplicação de revisão na Loja. Teste recusa de assinatura alterada, revisão antiga e catálogo expirado. Confirme backup e restauração antes de colocar dados reais. A validação em laboratório não substitui esses testes no domínio publicado.

## Backup cifrado e restauração

Prepare um diretório privado com modo 0700, fora da raiz pública. Execute `php bin/backup.php create /caminho-privado/catalogo.lbr /caminho-privado/backup.key`. A primeira execução gera uma chave de backup com modo 0600; as seguintes a reutilizam. A cópia contém tabelas e chave de assinatura, protegidas por criptografia autenticada. O comando não substitui arquivos existentes e imprime apenas tamanho e checksum.

Guarde a cópia e a chave em locais protegidos separados, incluindo uma cópia externa à hospedagem. Perder a chave impede a restauração. Para restaurar, configure uma instalação com banco exclusivo vazio, a mesma identidade `source_id` e um novo caminho privado para a chave de assinatura. Execute `php bin/backup.php restore /caminho-privado/catalogo.lbr /caminho-privado/backup.key`. Bancos com tabelas existentes são recusados; sessões administrativas não são restauradas. O utilitário aceita cópias de até 64 MiB. Valide a publicação assinada e o login antes de direcionar o domínio ao destino restaurado.
