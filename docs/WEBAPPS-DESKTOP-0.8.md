# Preferências web e tarefas da área de trabalho — 0.8

Este documento descreve os componentes implementados para integração e seus limites de validação. A conclusão da distribuição depende dos ensaios da imagem integrada.

## Perfis web

O botão **Preferências** está disponível no gerenciador, no seletor de perfis e no controle exibido dentro do aplicativo web. O comando `linuxbr-webapps --preferences IDENTIFICADOR` abre o mesmo diálogo.

- **Downloads:** abre `chrome://settings/downloads` com o diretório Chromium do perfil escolhido. Pasta de destino e confirmação antes de salvar permanecem sob controle do navegador.
- **Permissões do site:** abre as permissões nativas da origem inicial do aplicativo, no mesmo perfil, incluindo notificações, câmera e microfone. As categorias gerais e outros sites podem ser consultados pelas configurações do Chromium. As permissões não são concedidas silenciosamente.
- **Iniciar com a sessão:** cria um lançador individual em `$XDG_CONFIG_HOME/autostart`. Cada perfil é escolhido separadamente. Desmarcar remove somente esse lançador; remover um perfil do menu também interrompe sua abertura automática.
- **Links externos:** o padrão preserva o comportamento do perfil. A opção de navegador padrão trata cliques simples em links HTTP/HTTPS para outros hosts após recarregar a página. Os hosts adicionais conhecidos do serviço permanecem no perfil. Consultam-se tanto o navegador configurado quanto a associação efetiva do esquema; lançadores de aplicativos web e caminhos de perfis dedicados são recusados para impedir retorno ao mesmo fluxo.

A escolha de links não modifica redirecionamentos de autenticação, navegação programática ou cliques com teclas modificadoras. Um site que trate seus próprios cliques pode manter a navegação sob controle dele. Se a abertura externa falhar antes do encaminhamento, a página oferece **Abrir neste perfil**. Não há captura de cookies, formulários, contas ou histórico.

O host identifica o perfil pela ancestralidade do processo Chromium. Mensagens da extensão não escolhem outro perfil por identificador fornecido pela página. Apenas HTTP/HTTPS sem credenciais no endereço são aceitos no encaminhamento. Parâmetros e fragmentos do link clicado são mantidos; a URL não é montada como comando de shell.

As preferências do lançador ficam em `launcher-preferences.json`, ao lado de `app.json`. O diretório `profile`, os cookies, os favicons e a escolha de perfil padrão existente são preservados. Renomear atualiza o nome do lançador de inicialização. O seletor continua permitindo marcar e abrir vários perfis simultaneamente.

Cancelar o diálogo descarta suas escolhas de abertura automática e de links. Alterações já aplicadas nas janelas nativas do Chromium seguem as regras do navegador, conforme informado na tela.

## Pesquisa e inicialização

`desktopflows08.DesktopFlowsPage` pode ser incorporado à Central do Sistema. O executável `linuxbr-desktop-flows` deve chamar `desktopflows08.py`; aceita `--page search`, `startup`, `defaults` ou `transfers`.

A pesquisa envia o termo ao KRunner como um único argumento e oferece acessos relacionados a termos em português, inclusive nomes usados no Windows. Os resultados completos, seu tipo e sua localização são apresentados pela interface nativa. O Baloo continua responsável pelo índice; inclusão/exclusão de pastas, conteúdo indexado e suspensão da indexação permanecem nas preferências nativas. A tela consulta o estado real de `balooctl6 status` sob demanda e oferece o editor dos atalhos existentes. Não altera combinações de teclas nem reindexa arquivos automaticamente.

A lista de inicialização respeita a precedência de `$XDG_CONFIG_HOME/autostart` sobre os diretórios de `$XDG_CONFIG_DIRS`. Mostra nome, origem, caminho, comando declarado e condições do lançador. `Hidden`, restrições de ambiente, `TryExec` e condições nativas são considerados. Itens marcados para outro mecanismo da sessão são identificados e não recebem o controle de ativação/desativação desta tela.

Desativar um lançador do sistema cria uma substituição na conta atual; o arquivo de origem permanece intacto. Antes da primeira alteração, preserva-se o conteúdo anterior da conta em `$XDG_STATE_HOME/linuxbr/desktop-flows/autostart`. **Restaurar estado anterior** recupera esse conteúdo ou remove a substituição criada. Uma alteração posterior feita por outro programa impede a restauração e novas edições por esta tela, evitando sobreposição silenciosa. Arquivos que são links na configuração pessoal não são sobrescritos.

As alterações valem para a próxima entrada na sessão. Não encerram processos, não editam serviços de sistema ou de usuário e não estimam impacto de inicialização. Aplicativos restaurados pela sessão anterior têm acesso separado às preferências do KDE. O diagnóstico do lançador é aberto no módulo nativo quando o ambiente oferece seus registros.

## Aplicativos padrão, Abrir com e cópias

Navegador e outros padrões gerais abrem `kcm_componentchooser`; extensões e ordem dos aplicativos abrem `kcm_filetypes`. Para um arquivo escolhido explicitamente, `xdg-mime` consulta seu tipo e o aplicativo padrão, altera a associação e confirma o resultado por nova consulta. A lista inclui lançadores registrados nos diretórios XDG, inclusive lançadores Windows em subdiretórios; prioriza os que declaram suporte ao tipo. Destinos web dependem desse registro e não são tratados como leitores de qualquer formato.

**Abrir arquivo para testar** pede confirmação e solicita a abertura ao sistema. **Desfazer última associação** restaura e confere o aplicativo anterior, desde que a associação não tenha sido modificada por outro programa. Se o sistema não informava um aplicativo anterior, essa ação não inventa um padrão: ajustes adicionais são feitos no editor nativo. O menu **Abrir com** do Explorador continua oferecendo a experimentação por arquivo.

A aba **Cópias e conflitos** explica a fila KIO do Explorador e abre o gerenciador de arquivos e as preferências de notificações. Progresso, falhas parciais, conflitos e eventual pausa continuam no componente nativo da operação. A tela não apresenta uma segunda fila nem oferece pausa quando o protocolo não a suporta. Comparação detalhada depende de um comparador instalado.

## Acessibilidade

Os novos diálogos usam controles Qt com navegação por Tab, rótulos de acessibilidade e foco visível. As preferências e páginas incorporadas têm rolagem; os comandos do gerenciador foram distribuídos em três colunas para acomodar texto ampliado. `Ctrl+F` leva à pesquisa do gerenciador. No seletor, Espaço marca perfis, Enter aciona a abertura dos selecionados e Escape cancela. Texto de nome e caminho é apresentado como texto simples.

## Integração e dependências

Arquivos de implementação:

- `usr/lib/linuxbr-system/webapps.py`, `webapps_backend.py` e `webapps_host.py`;
- `usr/lib/linuxbr-system/desktopflows08.py` e `desktopflows08_backend.py`;
- extensão em `usr/share/linuxbr/webapps`, com a identidade de registro nativo preservada.

Componentes utilizados: Chromium, Python 3, PyQt6, `xdg-utils`, `kde-cli-tools` (KCMs e identificação de tipos), `plasma-workspace` (KRunner e sessão), Baloo (`balooctl6`) e Dolphin/KIO. Os acessos verificam a presença do executável. Um componente ausente produz mensagem explícita, sem substituir a ação por outro aplicativo. Os nomes dos KCMs foram conferidos: `kcm_autostart`, `kcm_baloofile`, `kcm_plasmasearch`, `kcm_keys`, `kcm_componentchooser`, `kcm_filetypes`, `kcm_notifications` e `kcm_smserver`.

## Validação

A extensão mantém a identidade dos perfis ao atualizar. Sua revisão 0.8.0.1 usa uma entrada de inicialização nova para que perfis existentes carreguem também o componente atualizado guardado pelo Chromium. Após instalar a atualização, feche e reabra as janelas do Chromium. Cookies, dados dos sites e destinos de download são preservados.

Ensaios isolados em 3 de novembro de 2026, em ambiente de laboratório com Qt sem janela e diretórios HOME/XDG temporários:

- `tests/test-webapps-desktop-08.py`: 14 testes; permissões/downloads no perfil correto, preservação de dados, inicialização individual, recuperação exata do lançador, condições e proteção contra edições externas, restrição de mensagens, bloqueio de retorno por handlers, seleção múltipla, teclado e componentes incorporados.
- `tests/test-webapps-settings-08.mjs`: encaminhamento das cinco páginas nativas pela extensão, com validação da seção e da origem e apresentação de falhas. O encaminhamento não modifica o arquivo de preferências do Chromium.
- O mesmo conjunto faz uma alteração real com `xdg-mime`, verifica a consulta do arquivo com acentos e espaços e restaura a associação anterior, usando somente configurações temporárias.
- Regressões anteriores: 11 testes do backend web, 6 de perfis 0.7, 4 da interface e 5 de favicons.
- Suítes de eventos da extensão e regras do catálogo executadas com sucesso.
- Capturas das novas preferências, gerenciador e lista de inicialização inspecionadas em tamanho compatível com o desktop de 1280×768.

Os ensaios não abrem câmera, microfone ou contas pessoais, nem alteram a sessão de trabalho. A validação integrada ainda deve exercitar a página nativa do Chromium em dois perfis reais, o encaminhamento para o navegador padrão, entrada em uma nova sessão e transferências locais/SMB pela fila KIO. Acesso ao módulo nativo não constitui, por si só, homologação de hardware ou de todos os serviços web.

## Referências técnicas

- [Inicialização de aplicativos pelo padrão XDG](https://specifications.freedesktop.org/autostart-spec/latest/).
- [Configurações nativas de sites no Chromium](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/chrome/browser/resources/settings/site_settings/README.md).
- [Associações de arquivos do KDE](https://docs.kde.org/trunk_kf6/en/kde-cli-tools/kcontrol6/filetypes/).
