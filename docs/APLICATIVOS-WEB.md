# Aplicativos web — perfis no pacote Linux BR 0.4.6

O Linux BR usa o Chromium do Debian, com suas atualizações de segurança e sandbox.
A extensão local **Aplicativos web Linux BR** identifica serviços durante a navegação
e oferece uma janela própria com atalho no menu. Não é uma versão modificada do
motor Chromium nem uma instalação do programa Windows do fornecedor.

## Como usar

1. Abra o Chromium e visite o serviço. Para serviços reconhecidos sem aplicativo
   Linux oficial no catálogo, aparece uma sugestão de instalação.
2. Escolha **Ver instalação** na notificação, ou abra **Aplicativos web Linux BR**
   pelo botão de extensões do Chromium. Você pode fixar esse botão na barra.
3. Confira o nome e o domínio na janela do Linux BR e clique em **Instalar aplicativo**.
4. Procure o aplicativo no menu. Ele abre uma janela Chromium própria, com login
   separado do navegador e dos demais aplicativos.

O gerenciador **Aplicativos web**, também disponível na Central do Sistema,
permite adicionar um endereço HTTPS manualmente, abrir aplicativos e remover
seus atalhos. Remover do menu preserva o perfil, recuperável em **Restaurar sessão**.

## Várias contas do mesmo site

Em **Aplicativos web**, selecione WhatsApp (ou qualquer outro aplicativo) e clique
em **Nova sessão**. Informe um nome, como **Pessoal**, **Trabalho** ou **Loja**.
Na primeira abertura, entre na conta desejada. Cada sessão possui sua própria
pasta Chromium, cookies e armazenamento, e pode abrir ao mesmo tempo que as
demais. Fechar a janela não apaga os dados; o serviço ainda pode expirar ou
revogar o login e solicitar nova autenticação.

O menu mostra um único atalho por aplicativo, como **WhatsApp**. Os atalhos
internos de cada perfil ficam ocultos do menu, sem apagar dados existentes.
O nome é informado por você; o Linux BR não lê o telefone, e-mail, senha ou
identidade da conta no site. **Renomear** altera a identificação sem mudar a
pasta do perfil. Perfis existentes continuam no mesmo local, identificados
inicialmente como **Principal**, preservando seus dados.

A loja oferece **Nova sessão / outra conta** nos webapps já instalados. Ao abrir
pelo menu ou pela loja, um único perfil abre diretamente; havendo vários,
uma caixa central lista os nomes com caixas de seleção. Marque um ou mais e
clique em **Abrir selecionados**; cancelar não abre nenhum perfil.

Dentro de cada webapp aparece o nome do perfil e **+ Novo perfil**. O mesmo
botão existe no seletor. Informe o nome e confirme **Criar e abrir perfil**:
uma nova janela abre o endereço inicial salvo, com armazenamento separado e
sem copiar o login atual. Os demais perfis permanecem abertos. O controle
pode ser arrastado pelo nome, para não cobrir partes importantes do site.
Ele aparece apenas nos perfis dedicados do Linux BR, não na navegação comum.
A criação sempre exige confirmação; a extensão não aceita um caminho de perfil
ou URL da página para substituir a identidade verificada pelo processo Chromium.

Remover um atalho não encerra a sessão no serviço nem apaga o
perfil: use **Restaurar sessão** para recuperá-lo. A interface não permite dois
perfis do mesmo site com o mesmo nome, para evitar confusão.

### Validação da atualização de sessões

- 11 testes de backend, 4 de interface webapps e 4 da loja passaram, além dos
  testes JavaScript de regras e eventos da extensão.
- O teste com Chromium real abriu dois perfis simultâneos, gravou cookies
  persistentes e localStorage diferentes e confirmou isolamento e persistência
  após fechar e reabrir os dois navegadores. Foi usado um site HTTPS de teste;
  nenhuma conta real foi autenticada.
- Duas instâncias WhatsApp foram abertas com diretórios distintos.
- Na VM UEFI, o seletor abriu Pessoal e Trabalho juntos. O botão dentro do
  WhatsApp criou Loja e abriu imediatamente outra janela na página inicial.
- A extensão usa uma nova URL de service worker na versão 0.4.6 para substituir
  o worker antigo em perfis persistentes, sem apagar seus dados.
- O pacote final 0.4.6 foi instalado na VM UEFI e passou em `dpkg -V linuxbr-system`.

Pacote no computador de desenvolvimento:
`/home/emericv/git/linuxbr/dist/session-packages-0.4.6/linuxbr-system_0.4.6_all.deb`.
Esta etapa atualizou o código e o pacote instalado. A ISO 0.4.4 existente não foi
regerada; o fluxo de perfis entrará na próxima compilação da ISO com o código 0.4.6.

## Identificação e disponibilidade Linux

- O catálogo inicial reconhece WhatsApp Web, Microsoft Teams e Canva. Ele usa
  domínios exatos, links oficiais e uma data de revisão.
- Spotify, Discord, Telegram e Slack são identificados como serviços com opção
  Linux, portanto não recebem oferta automática de webapp.
- Atalhos conhecidos de aplicativos já instalados, inclusive alguns clientes
  comunitários, também suprimem a sugestão.
- Um site desconhecido com manifesto PWA e modo de janela recebe indicação no
  botão da extensão, com a informação **versão Linux não confirmada**. Não recebe
  a notificação automática reservada ao catálogo.
- Não é possível deduzir de qualquer página a inexistência de um aplicativo Linux.
  O catálogo é conservador e precisa de manutenção quando fornecedores mudarem
  suas ofertas. Ele não é uma busca completa no Debian, Flathub ou na internet.

## Preferências e privacidade

A extensão pode ser desativada pelo controle **Sugerir aplicativos ao navegar**.
**Não sugerir este site** guarda a escolha localmente. Uma oferta automática não
se repete para o mesmo serviço durante sete dias. As escolhas podem ser redefinidas.

A identificação usa o domínio e metadados do manifesto, sem ler formulários,
senhas, cookies ou conteúdo de documentos. Não envia histórico a um serviço do
Linux BR. A extensão não atua em janelas anônimas. Ela mantém temporariamente
os candidatos das abas na memória da sessão e guarda localmente domínios ignorados
e datas das sugestões. O Chromium continua tendo suas próprias preferências de histórico.

Somente manifestos HTTPS da mesma origem são lidos, com limite de tamanho e tempo,
sem credenciais. Endereços de instalação não incluem query strings ou fragmentos,
para evitar preservar tokens de login. O usuário sempre confirma a instalação numa
janela do sistema. Não há instalação silenciosa por páginas nem comandos recebidos
da internet. A ponte nativa só aceita consulta, oferta de confirmação e abertura
do gerenciador; não oferece execução de comandos arbitrários.

## Perfis e atualização

Os registros, ícones e perfis ficam em `~/.local/share/linuxbr/webapps/<id>/`;
os atalhos ficam em `~/.local/share/applications/linuxbr-webapp-<id>.desktop`.
O local acompanha `XDG_DATA_HOME` quando definido. O perfil não compartilha login
com o Chromium normal. Permissões de câmera, microfone e notificações são solicitadas
pelo navegador. O modo offline, chamadas, DRM e recursos de cada serviço dependem
da implementação do site; uma janela de aplicativo não adiciona recursos ausentes.

Novas contas usam Chromium como navegador inicial; preferências pessoais de contas
existentes não são reescritas. O Firefox permanece disponível. A identificação
automática ocorre apenas no Chromium com a extensão Linux BR carregada.

## Manutenção e testes

O catálogo e a extensão ficam em `packages/linuxbr-system/files/usr/share/linuxbr/webapps/`.
A chave pública no manifesto fixa a identidade da extensão; a ponte registra apenas
essa identidade. O diretório `/usr/share/chromium/extensions/` carrega a extensão
junto da integração KDE, sem substituir a lista de extensões do Debian.
Esse mecanismo é específico do Chromium Debian e não depende da loja do Google Chrome.

Testes: `python3 tests/test-webapps.py`, `python3 tests/test-webapps-gui.py`,
`node tests/test-webapps-rules.mjs` e `node tests/test-webapps-events.mjs`.

Validação em 28/10/2026, com Chromium Debian 156.0.8078.47:

| Verificação | Resultado |
| --- | --- |
| Backend e integração de arquivos | 9 testes aprovados |
| Confirmação e gerenciamento com Qt real | 3 testes aprovados |
| Regras de classificação e eventos de navegação | Aprovados, incluindo redirecionamento SPA e oferta única |
| Extensões Linux BR e integração KDE | Carregadas juntas pelo mecanismo Debian |
| WhatsApp | Reconhecido; confirmação abriu; atalho instalado e janela própria aberta |
| Canva | Sugestão automática exibida; preferência de ignorar site gravada |
| Spotify | Identificado automaticamente após redirecionamento; nenhuma oferta de webapp |
| PWA genérico de teste | Manifesto reconhecido, disponibilidade Linux desconhecida, sem oferta automática |
| Privacidade do endereço | Query string e fragmento descartados do endereço instalado |
| Desativar sugestões | Candidatos e notificações removidos; estado persistido por perfil |
| Aplicativo já instalado | Não oferecido novamente |
| Pacotes 0.4.3 no sistema UEFI instalado | Instalados e verificados, incluindo propriedade do link da extensão |
| ISO 0.4.3 | Compilação, configuração do sistema de arquivos, checksum e entradas de boot aprovados |
| Boot UEFI da ISO nova | Área de trabalho em 1280×768; Chromium no painel e extensões Linux BR/KDE carregadas |
| Instalação na ISO Live nova | Canva reconhecido; confirmação e instalação concluídas; atalho visível no menu |
| Boot BIOS, checagem final | Área de trabalho em 1280×768 |

Os serviços foram testados sem autenticar contas. Chamadas, DRM, recursos pagos
e funcionamento offline não foram homologados. O PWA genérico usou um servidor
HTTPS local e certificado de teste restrito ao navegador de teste; a configuração
distribuída não inclui exceções de certificados nem depuração remota.

Imagem no computador de desenvolvimento: `/home/emericv/git/linuxbr/dist/linuxbr-0.4.3-amd64.iso` (3,3 GB).

SHA-256: `5c8221b9bc23fc8f7e28a7a629eb8a09093a820ee9dfae0b62944d6b2ac874fa`.

Fontes do catálogo:

- [WhatsApp: plataformas e versão web](https://www.whatsapp.com/download/)
- [Teams: aplicativo web para Linux](https://www.microsoft.com/en-us/microsoft-teams/download-app)
- [Canva: downloads](https://www.canva.com/download/)
- [Spotify para Linux](https://www.spotify.com/download/linux/)
- [Discord](https://discord.com/download)
- [Telegram Desktop](https://desktop.telegram.org/)
- [Slack para Linux](https://slack.com/downloads/linux)
- [Ponte nativa do Chromium](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)
