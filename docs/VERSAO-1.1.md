# Linux BR 1.1 — Preparar para trabalho ou escola

**Estado da Alpha 1.** **Preparar para trabalho ou escola** consulta o perfil assinado da máquina, mostra a revisão e prepara as preferências da conta. O ingresso no Active Directory permanece disponível em **Configurações → Contas → Organização**. As etapas corporativas previstas para a homologação completa estão descritas abaixo.

Uma pessoa deve conseguir entrar com sua conta de trabalho ou escola e receber o ambiente definido pela organização. A tela de preparação mostra o que já está pronto, o que está sendo configurado e o que depende de uma ação. A foto de referência, `227592.heic`, mostra esse fluxo com a configuração da conta expandida e estados separados para ingresso na organização, políticas, certificados, conexões e aplicativos.

## Jornada

1. No primeiro uso, **Preparar meu computador** oferece **Uso pessoal** e **Trabalho ou escola**. Em uma instalação existente, o fluxo também pode ser iniciado em **Configurações → Contas → Organização**.
2. A pessoa identifica a organização pelo domínio ou recebe da equipe de TI um perfil de configuração assinado. O sistema exibe a identidade da organização, a origem do perfil, o que será configurado para a máquina e o que se aplica somente à conta. A pessoa revisa e confirma antes da aplicação.
3. Em um computador ainda não vinculado, uma conta autorizada faz o ingresso no domínio com a aprovação administrativa local. Em um computador já vinculado, o fluxo reutiliza esse vínculo e orienta a pessoa a entrar com a própria conta na tela de login. Depois da autenticação, a preparação retoma no ponto correto.
4. A tela **Configurando para trabalho ou escola** agrupa as etapas por **Dispositivo** e **Conta**. Cada grupo pode ser expandido e cada item tem ícone, descrição e estado textual. Ao terminar, a pessoa vê um resumo do que ficou disponível, das pendências e do próximo passo.

## Escopo proposto para a 1.1

| Etapa | Comportamento esperado |
| --- | --- |
| Conta e organização | Reaproveitar o ingresso em Active Directory via realmd/SSSD. Conferir rede, DNS e horário antes do ingresso. Criar o diretório pessoal pelo fluxo de login do sistema e manter uma conta administrativa local para recuperação. |
| Políticas | Consultar o serviço da organização e aplicar regras assinadas por dispositivo e por conta. Mostrar a revisão aplicada e a origem das regras. Uma política obrigatória sem suporte ou com falha mantém o preparo pendente. Consulte [Políticas da organização](POLITICAS-CORPORATIVAS-1.1.md). |
| Certificados | Conferir assinatura, validade, finalidade e origem. Mostrar quais certificados passam a ser confiáveis e em qual escopo. Exigir autorização administrativa para modificar a confiança do dispositivo. |
| Conexões | Configurar perfis suportados de Wi-Fi ou VPN e disponibilizar atalhos para pastas de rede. Mostrar quando uma conexão inicial é necessária antes do primeiro login corporativo. |
| Aplicativos | Abrir a fila da Loja Linux BR para provisionar aplicativos Linux e webapps de fontes aprovadas. Mostrar o progresso por aplicativo e indicar quando a própria pessoa precisa entrar no serviço. Manter os perfis web separados por conta do sistema. |
| Ambiente de trabalho | Aplicar atalhos, pastas de trabalho e preferências iniciais previstas no perfil, respeitando a separação entre contas locais e corporativas e preservando arquivos pessoais. |

O primeiro recorte usa Active Directory, um perfil de cadastro assinado pela equipe de TI e um serviço de políticas hospedado na própria organização. O perfil estabelece o vínculo e a confiança inicial. O serviço distribui as revisões posteriores e oferece um painel para atribuições e auditoria. Integrações específicas com Microsoft Entra ID ou Intune ficam como possíveis evoluções. O login do sistema e o login de aplicativos são etapas distintas. Cada aplicativo pede autenticação pelo fluxo do seu provedor quando necessário.

## Progresso, interrupções e segurança

- Mostrar **Aguardando**, **Em andamento**, **Ação necessária**, **Concluído**, **Falhou** ou **Adiado** conforme o resultado real da etapa. Usar progresso indeterminado enquanto o total for desconhecido. Exibir a etapa em execução, a mensagem de erro e a ação disponível.
- Salvar progresso por dispositivo e por conta, vinculado à revisão do perfil. Retomar após queda de rede, encerramento da sessão ou reinício. Uma nova tentativa confere o estado atual e aplica somente o que falta, sem duplicar vínculos, certificados, aplicativos ou atalhos.
- Permitir adiar itens opcionais. Se um requisito obrigatório falhar, indicar que o ambiente de trabalho segue pendente e oferecer nova tentativa ou acesso à recuperação pela conta local. Se houver reinício, explicar o motivo e pedir confirmação.
- Validar o perfil com uma chave previamente confiável antes de aplicar alterações. Usar operações conhecidas e parâmetros validados. Ingresso, certificados de máquina, políticas globais e instalações de sistema exigem autorização administrativa pelos mecanismos do Linux BR.
- Usar PAM para o login e o cofre da sessão para credenciais que precisem ser guardadas. Excluir senhas, tokens e chaves privadas dos arquivos de progresso, argumentos de processos e relatórios exportáveis.
- Oferecer **Desconectar organização** na Central. Antes de confirmar, listar os recursos gerenciados que serão removidos e o impacto no próximo login. Preservar arquivos pessoais, contas locais e configurações que já existiam.

## Critérios de aceite

1. Em instalação limpa, vincular um computador de laboratório ao domínio, fazer o primeiro login com conta corporativa sem privilégios administrativos e concluir o preparo com o perfil assinado.
2. Em máquina já vinculada, preparar duas contas corporativas e conferir a separação de progresso, atalhos, credenciais e sessões de webapps. Confirmar que o fluxo pessoal continua disponível na conta local.
3. Interromper a rede durante uma instalação e reiniciar antes de concluir. Confirmar que o progresso é retomado, que somente as etapas pendentes são reaplicadas e que o estado final confere com os recursos realmente disponíveis.
4. Recusar perfil adulterado ou assinado por chave desconhecida antes de alterar o sistema. Testar certificado vencido, política obrigatória sem suporte e pacote indisponível. Conferir mensagens, tentativas e ausência de segredos no diagnóstico.
5. Desconectar a organização com confirmação e conferir a preservação dos arquivos pessoais e do acesso local. Validar navegação por teclado, foco, leitura dos estados e uso em 1280 × 768.

## Manutenção e suporte

A primeira prioridade é entregar o ciclo de atualização em ondas, diagnóstico para suporte e recuperação após uma atualização com problema. O inventário básico e a migração guiada do Windows completam o escopo em seguida. Consulte os [requisitos e critérios de aceite de manutenção](MANUTENCAO-1.1.md).

## Loja — Snap e Homebrew

Adicionar **Snap Store** e **Homebrew** como fontes opcionais em **Loja → Fontes**. Mostrar o estado de cada integração e pedir confirmação para habilitá-la ou instalar seus pré-requisitos. Reutilizar a busca, a biblioteca, a fila e o histórico da Loja. Para aplicativos disponíveis em mais de um formato, mostrar as opções com origem, mantenedor, versão, escopo e estado da instalação. A pessoa escolhe a fonte antes de instalar. Atualizações e remoções usam a fonte da instalação existente.

A configuração, a política local, a lista de reinstalação e os ensaios realizados estão descritos em [Fontes opcionais e listas de aplicativos](LOJA-FONTES-OPCIONAIS-1.1.md).

- **Snap Store.** Integrar pesquisa, instalação, atualização e remoção pelo snapd. Mostrar publicador, canal, revisão e confinamento. Usar o canal estável por padrão e pedir confirmação específica para o modo `classic`, com indicação do acesso ampliado e das restrições da organização. Conferir o suporte do sistema ao confinamento e mostrar atualizações automáticas ou adiadas conforme o estado reportado pelo snapd. Aplicativos gráficos devem aparecer no menu Iniciar. [Confinamento Snap](https://snapcraft.io/docs/explanation/security/snap-confinement/) · [Atualizações Snap](https://snapcraft.io/docs/how-to-guides/manage-snaps/manage-updates/)
- **Homebrew.** Começar pelas fórmulas do catálogo oficial compatíveis com Linux. Detectar uma instalação existente e operar como a conta proprietária autorizada do prefixo, sem executar `brew` como root nem mudar a propriedade do prefixo. Oferecer instalação guiada quando necessário, com confirmação do método e dos pré-requisitos. Mostrar fórmulas de terminal em uma categoria própria e orientar como executá-las no Terminal Linux BR. Casks de macOS e taps de terceiros ficam fora do primeiro recorte. [Homebrew no Linux](https://docs.brew.sh/Homebrew-on-Linux)
- **Máquinas gerenciadas.** A TI pode habilitar ou desabilitar cada fonte na Loja e restringir instalações gerenciadas. Separar o estado e o calendário de cada gerenciador das ondas APT. Exibir como pendente qualquer controle corporativo que não possa ser garantido no gerenciador de origem.

**Critérios de aceite**

1. Em instalação limpa, habilitar cada fonte separadamente, instalar, atualizar e remover um Snap gráfico e uma fórmula Linux. Confirmar o atalho do Snap no menu, a execução da fórmula pelo terminal e o histórico por fonte.
2. Detectar programas instalados antes da habilitação. Quando houver o mesmo aplicativo em mais de uma fonte, atualizar ou remover apenas a instalação selecionada.
3. Simular fonte indisponível, instalação interrompida e tentativa de instalar um Snap `classic` sujeito a bloqueio. Mostrar o erro e o caminho para retomar sem duplicar a operação.

### Exportar e reinstalar aplicativos

A implementação cobre aplicativos Flatpak de fontes HTTPS já configuradas e verificadas, Snap Store e Homebrew Core. Ela preserva o escopo e revisa a origem antes de enfileirar. Reinstalações que dependem de um gerenciador, canal ou confinamento indisponível aparecem como ações manuais. DEB, webapps e Wine são referências pesquisáveis na Loja para escolha manual.

- Em **Loja → Biblioteca**, permitir selecionar aplicativos instalados e exportar uma lista em arquivo JSON com formato versionado. Registrar o identificador do pacote, formato, origem e escopo da instalação, além da versão instalada para consulta. A lista contém apenas os dados necessários à reinstalação. Contas, senhas, tokens, arquivos pessoais e configurações dos aplicativos ficam de fora.
- Na importação, mostrar uma prévia com aplicativos já instalados, disponíveis, indisponíveis ou com origem desabilitada. A pessoa pode selecionar o que deseja reinstalar e conferir a origem e a versão disponível antes de confirmar. Uma alternativa de formato ou fonte exige escolha explícita. As políticas da organização valem também para as instalações importadas.
- Validar o arquivo e resolver os identificadores nas fontes habilitadas da Loja. A lista não pode executar comandos, ativar fontes nem instalar a partir de endereços arbitrários. Usar a fila da Loja e permitir retomar após falha, identificando os itens já concluídos.

**Aceite.** Exportar uma seleção com aplicativos de formatos diferentes e importá-la em outra instalação, incluindo um item já presente e outro com origem desabilitada. Conferir que a fila recebe apenas os itens aprovados e que repetir a importação não duplica instalações. Verificar que um arquivo inválido é recusado antes de alterar a máquina.

### Mostrar quais formatos foram testados

A janela de operações exibe o estado por destino. A correspondência para aprovação da versão usa origem e commit Flatpak. O ensaio Homebrew de laboratório identifica o pacote e a arquitetura separadamente. A homologação da candidata depende dos testes vinculados aos artefatos publicados.

- Exibir o resultado na ficha de cada formato e origem, ao lado da opção de instalação. Usar estados distintos para **Testado**, **Testado com limitações**, **Falhou no teste** e **Sem teste para esta versão**. A aprovação de um formato vale para a combinação verificada de aplicativo, origem, versão e arquitetura.
- Informar a versão do Linux BR, a versão testada do aplicativo, a data, as funções verificadas, as limitações e a referência da evidência. Se o aplicativo ou o Linux BR mudar de versão, identificar o ensaio como histórico até haver uma validação correspondente. Manter os resultados de teste separados das informações publicadas pela fonte.

**Aceite.** Abrir a ficha de um aplicativo que tenha dois formatos e validar que cada um exibe seu próprio resultado. Atualizar a versão disponível em uma das fontes e conferir que a Loja identifica o teste anterior como histórico, sem atribuir seu resultado à nova versão ou ao outro formato.

## Regressão obrigatória — compartilhamento da tela inteira

Em 9 de novembro de 2026, o portal KDE registrou que a interface de captura do Wayland estava indisponível, embora PipeWire e WirePlumber estivessem ativos. Reiniciar apenas o portal restaurou a criação da sessão de captura e a seleção de monitor pela API. Os registros também mostram uma queda posterior do KWin durante as tentativas de compartilhamento. A causa da queda e a causa da indisponibilidade inicial precisam ser reproduzidas e investigadas separadamente antes de considerar a regressão corrigida.

A Alpha 1 exige KWin `4:6.3.6-1+deb13u1` ou posterior. Essa atualização do Debian corrige uma queda ao desconectar ou reconectar uma saída de vídeo. A compilação inclui o conjunto de pacotes corrigidos com verificação pelo índice assinado do Debian enquanto a atualização estiver na área de propostas. O ensaio de captura continua obrigatório. [Correção do Debian](https://bugs.debian.org/1150678)

Na ISO candidata, validar pelo Chromium em Plasma Wayland, com confirmação normal no seletor de compartilhamento. Selecionar **Tela inteira**, confirmar que o monitor correto fornece quadros de vídeo que acompanham uma mudança visível na tela, encerrar e iniciar outra captura. Conferir que a sessão gráfica permanece ativa e que cancelar no seletor encerra a solicitação sem iniciar captura. Repetir estes ensaios:

- `screen-sharing-first-login` — primeiro login em uma instalação limpa, com o portal iniciado pelo fluxo normal.
- `screen-sharing-after-output-change` — após alterar a resolução e reconectar uma saída, cobrindo a situação em que o monitor desaparece e reaparece.
- `screen-sharing-after-relogin` — após encerrar e iniciar a sessão novamente.

Executar os cenários em laboratório e repetir em hardware físico representativo. Registrar o hash da ISO, versões dos componentes, modo de sessão, resultado da captura e registros do portal e do KWin. O relatório deve identificar falhas mesmo quando o seletor abre normalmente. Aprovação exige captura de ponta a ponta sem reiniciar serviços manualmente e sem queda do compositor. A publicação estável exige evidência aprovada para os três cenários, vinculada à ISO publicada.

Pontos de partida: [preparação inicial](INSTALACAO-1.0.md), [contas e domínio](USUARIOS-E-DOMINIO.md), [cofre da sessão](CREDENCIAIS.md) e [Loja Linux BR](LOJA-DE-APLICATIVOS.md).
