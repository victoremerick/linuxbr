# Linux BR 0.9 — desenvolvimento

Estado: implementação parcial, sem nova ISO ou publicação no repositório APT.

## Primeira etapa

- Nova página de detalhes de conexão nas Configurações, substituindo a rota anterior para informações de rede. Consulta assíncrona, seleção de adaptador, campos IPv4/IPv6, gateway, DNS, MAC, driver e cópia dos detalhes.
- Nove atalhos diretos às Configurações no menu de aplicativos: ambiente, tarefas, serviços, inicialização, detalhes de rede, conexões, programas instalados, atualizações e IP/DNS.
- Formulário de criação de serviços pessoais e do sistema: programa, argumentos, pasta, conta, variáveis, reinício após falha e prévia. Criação parada e desabilitada por padrão.
- Propriedades de serviços: estados, conta, processo, memória, tempo de CPU, resultado, dependências e arquivos de configuração.
- Inventário de serviços inclui unidades instaladas ainda não carregadas, com coluna de inicialização e estados traduzidos.

## Verificações executadas

- Seis testes automatizados de leitura de rede e validação de definições de serviços passaram.
- Consulta real de rede: quatro adaptadores no hospedeiro e dois na VM.
- Construção das interfaces na VM com renderização fora da tela: formulário, detalhes de rede e inventário de 92 serviços pessoais. Capturas nesta pasta; não equivale a homologação completa da sessão gráfica.
- Criação e execução real de serviço pessoal; duplicata recusada; argumentos e variáveis com espaços, aspas, dólar, porcentagem e ponto e vírgula preservados literalmente. Pasta de trabalho com espaços validada.
- Criação, início e parada de serviço temporário do sistema executando como nobody. O teste encontrou aspas extras na descrição, corrigidas posteriormente e conferidas no teste pessoal.
- Serviços temporários removidos após os testes. Nenhum serviço de produção foi alterado.
- Fontes em área separada na VM; instalação estável e artefatos da 0.8.5 não substituídos.

## Segunda etapa

- Edição dos serviços criados pelo formulário, com preenchimento dos campos existentes, identificador preservado e revisão antes de salvar.
- Cópia da configuração anterior, restauração, validação antes de aplicar e reversão automática se o recarregamento falhar. Edições externas e gravações com versão desatualizada são recusadas.
- Alterar/restaurar uma definição não reinicia o processo atual; a interface informa quando será necessário reiniciar para aplicar.
- Página própria de Programas de inicialização, com busca, estado, origem, comando, caminho, habilitação/desabilitação e opção de desfazer.
- Entradas do sistema são preservadas: mudanças de login são preferências pessoais. Condições de ambiente de trabalho, TryExec, entradas ignoradas e arquivos inválidos aparecem explicitamente.
- Componentes de sessão/autenticação identificados como essenciais não podem ser desabilitados por esta página.
- A página encaminha para criação de aplicativos/scripts, serviços e tarefas. Os atalhos msconfig e shell:startup passam a abri-la. A central completa de modos de boot permanece pendente.

### Validações da segunda etapa

- 14 testes automatizados passaram: três de rede, cinco de serviços e seis de inicialização.
- Teste de falha no recarregamento confirmou restauração exata da definição anterior.
- Testes com diretórios isolados confirmaram precedência de entradas pessoais, preservação dos arquivos do sistema, restauração exata, recusa de alterações concorrentes, links e identificadores inválidos.
- Na VM, edição e restauração real de serviço pessoal preservaram o PID do processo. Repetido para serviço do sistema executando como nobody, também sem reiniciar o processo.
- Formulário de edição preservou os argumentos; gravação com hash desatualizado foi recusada.
- A nova tela abriu com 27 entradas de inicialização. Captura startup.png obtida por renderização fora da tela; não foi executado novo login para homologar todos os programas listados.
- Definições temporárias e backups dos serviços de teste foram removidos. Nenhuma entrada real de inicialização foi modificada.

## Pendências

- Serviços: overrides de unidades fornecidas por pacotes, importação/exportação, dependências configuráveis, limites, proteção de componentes essenciais nas ações de serviço e logs aprimorados.
- Rede: detalhes específicos de Wi-Fi, VPN, rotas e diagnóstico integrado.
- Completar a central de inicialização com opções de boot; recursos opcionais, recuperação/boot, edição Servidor e demais requisitos de VERSAO-0.9.md.
- Servidor PHP/MySQL/Angular e protocolo de catálogo/atualizações de webapps.
- Validação da integração completa, empacotamento, instalação, atualização e nova ISO.

Referência técnica da execução de serviços: https://freedesktop.org/software/systemd/man/latest/systemd.service.html

Referência da inicialização de aplicativos: https://specifications.freedesktop.org/autostart/latest/

## Terceira etapa — catálogo de webapps

- Servidor PHP/MySQL com publicações versionadas assinadas Ed25519, painel Angular, autenticação, papéis, proteção CSRF, auditoria, rascunhos, moderação e verificações limitadas por cron.
- Compilação Angular concluída. No laboratório: MySQL 8.4, PHP, HTTPS e navegação real no Chromium para catálogo público, login, edição de rascunho e histórico; sem erros JavaScript no roteiro.
- API validada com recusa de acesso anônimo ao painel, CSRF ausente, origem indevida, URL inválida e edição desatualizada. Assinatura conferida independentemente com OpenSSL.
- Loja integrada a fontes assinadas com confirmação de impressão digital, cache offline, revisões e notificações. Revisões de metadados não representam atualizações do código hospedado pelo fornecedor.
- Seis testes adicionais passaram na VM: assinatura alterada, expiração, revisão antiga/inconsistente, identidade, período de validade, formato e duplicatas.
- Ciclo real por HTTPS na VM: fonte adicionada, aplicativo instalado, revisão de nome aplicada e mudança de domínio recusada para aplicação automática. Arquivo sintético de sessão com 2.048 bytes preservado por hash em todas as etapas; isto não demonstra autenticação real em serviços externos.
- Hospedagem Hostinger ainda não publicada; domínio e acesso não foram informados. Instalador estável e ISO 0.8.5 preservados. Integração gráfica completa da Loja, rotação de chave, documentação e validações finais ainda em andamento.

## Quarta etapa — serviços e recursos

- Serviços: limites de memória, CPU e processos, dependências, isolamento opcional, importação/exportação, duplicação e remoção de definições próprias. Serviços de pacotes recebem overrides separados, com prévia, restauração e preservação do arquivo original. Componentes essenciais e aliases conhecidos são protegidos contra ações genéricas.
- Eventos com busca, exportação e atualização a cada cinco segundos somente enquanto a página estiver visível; limite de 500 registros.
- Teste real em serviço temporário: MemoryMax e TasksMax conferidos, override de memória aplicado e restaurado, PID preservado, remoção de serviço ativo recusada e remoção após parada concluída. Resíduos do teste removidos.
- Rede: rotas legíveis, máscaras IPv4, conectividade, fabricante/modelo e leitura dos detalhes Wi-Fi. Diagnóstico de conectividade e reativação com aviso de interrupção. Wi-Fi ainda testado por dados de referência; não há adaptador Wi-Fi exposto à VM.
- Nova página de recursos opcionais: inventário real de sete grupos, serviços, pacotes, espaço, planos de instalação/remoção e perfis de serviços. Renderização na VM passou; mutações e reversão da página ainda em validação. Indexação encaminhada à configuração da conta.
- Rotação explícita de chave do catálogo implementada e testada; a revisão mínima é preservada. Sete testes de catálogo passaram. Demais testes unitários: quatro de rede, nove de serviços e seis de inicialização.
- SSH da Hostinger validado; estrutura identificada sem alterar aplicações existentes. PHP 8.2 com PDO MySQL e cURL. Sodium disponível como extensão, carregamento padrão ainda pendente. Destino público/banco próprios ainda pendentes de definição.
- Correção de título/localização das Propriedades após Aplicar adicionada ao código nativo, ainda sem compilação e teste de integração nesta etapa.

## Quinta etapa — implantação e modos de inicialização

- Catálogo implantado em linuxbr.homedeveloper.com.br, com diretório público separado, banco exclusivo e chave/configuração fora da raiz pública. DNS criado e HTTPS válido confirmado pelo servidor. Publicação inicial ainda vazia; cadastro, integração oficial e validação pública completa pendentes.
- Extensão Sodium habilitada no PHP 8.2. Agendamento horário solicitado pelo painel, ainda sem confirmação da persistência.
- Navegação migrada para a API HTTP local do Chrome, perfil default. Acesso ao painel depende de conclusão da verificação de dois fatores nesse perfil.
- Teste real isolado confirmou bloqueio de serviço e socket por recurso opcional e restauração dos estados anteriores. Remoção de pacotes ainda depende da compilação com dependências reorganizadas.
- Estrutura dos geradores de inicialização restrita e console mínimo criada; ainda não instalada nem validada em boot. Nenhuma conclusão de versão ou ISO 0.9 é declarada nesta etapa.

## Sexta etapa — catálogo público e boot isolado

- Perfil home-developer-hostinger identificado e autenticado na conta correta. Agendamento horário do catálogo confirmado na tabela da Hostinger; não foi duplicado. Resultado automático do cron ainda vazio no painel, execução manual passou.
- HTTPS público, redirecionamento HTTP, descoberta, assinatura Ed25519, busca, login/logout, CSRF e recusa de origem indevida validados. PHP web usa 8.3; Sodium habilitado nessa versão além do CLI 8.2. Arquivos privados retornaram 404.
- WhatsApp e Notion publicados com URLs de referência e favicons oficiais. Imagens carregadas no navegador. Fonte oficial incluída no código do sistema com chave fixada, cópia assinada e respeito à remoção/desativação pelo usuário. Nove testes de catálogo passaram; cliente da VM conferiu a publicação 2 pelo HTTPS público.
- Central Configuração do Sistema implementada com cinco abas e abertura gráfica verificada; modos de boot exigem autenticação. Oito testes da política, geração de menu, preservação da raiz/initrd, configuração concorrente e restauração após falha passaram. Menu gerado a partir do kernel real passou pelo grub-script-check.
- Cópia de QA criada por reflink após desligamento limpo; QA original reiniciada, VM visível preservada. Primeiro boot restrito comprovou firewall e autenticação ativos, NetworkManager/SSH/cron/Samba/libvirt e serviço/socket/timer de teste bloqueados; unidade pessoal de teste também bloqueada. Nenhuma unidade em falha na coleta. Identificada duplicidade de sessão Wayland na configuração de manutenção; corrigida no código, ainda aguardando novo login de validação.
- Duas imagens antigas 0.7 Beta 3 foram removidas conforme autorização prévia, após verificar referências e arquivos abertos. O espaço disponível não aumentou na medição; não foi contabilizada liberação de armazenamento.
- Ainda pendentes: demais modos e login da manutenção, integração Shift+Reiniciar, edição Servidor, compilação completa, validações de instalação/atualização/restauração e demais itens do escopo. A versão 0.9 não está concluída nem publicada como ISO.

## Sessão Servidor e recuperação — 5 de novembro

- Perfil Hostinger confirmado: home-developer-hostinger, conta triativostore@gmail.com.
- Shift + Reiniciar na tela de login iniciou o ambiente de recuperação; autenticação, terminal e bloqueios de rede foram observados na cópia de QA.
- Sessão Servidor autenticada iniciou em X11 com Openbox, sem processos Plasma/KWin. Rede ativa; aproximadamente 625 MB de RAM em uso nesta VM de 4 GB, incluindo componentes de QA.
- Terminal de manutenção usa o mesmo perfil Bash do desktop, com caminho por letra dentro da janela. Evidência: servidor-terminal.png.
- Contas e identificação: criação de usuário temporário, associação ao grupo sudo, troca de senha e alteração de hostname conferidas; conta removida e nome original restaurado.
- Backup cifrado do catálogo copiado para D:/LinuxBR/servidor/catalogo e SHA-256 conferido. Acesso administrativo e chave ficam na subpasta privado, com permissões locais restritas.
- Primeiro ensaio de compilação encontrou origem incorreta do diálogo Plasma; o recurso pertence a plasma-workspace-data. Origem corrigida na segunda fonte congelada. A compilação source02 está em andamento; nenhuma ISO 0.9 foi publicada.
- Implementação nova ainda em validação: seleção de edição no Calamares, modos live, janela avançada de recuperação e separação de dependências do servidor.

## Retomada de 5 de novembro — atualização real

A VM isolada de atualização passou da base publicada 0.8.5 final7 para os 12 pacotes aplicáveis da candidata 0.9 source05. A instalação terminou com código zero, sem pendências no dpkg. Os 1.793 arquivos pessoais registrados antes da operação mantiveram seus hashes. O Timeshift criou automaticamente um ponto antes da atualização. O hook APT e sua política agora pertencem ao componente comum de inicialização, preservando a proteção na edição Servidor.

A compilação completa da candidata source06 foi iniciada em fonte congelada, SHA256 `a149a139b1d080d79811229e562d450e4640f07a4acd7003d6262b64f8148e95`. A ISO ainda não foi concluída nem publicada. A candidata acrescenta orientação de credenciais apenas na sessão temporária live, sem alterar a autenticação instalada.

As duas VMs antigas 0.8.5 final7 foram compactadas com comparação lógica e copiadas para `D:/LinuxBR/arquivo-vms-0.8.5`, com SHA256 conferido. Somente as duplicatas remotas verificadas foram removidas; firmware e discos de referência atuais foram preservados.

## Modos reais, Servidor e recursos opcionais

Os modos Segurança, Segurança com rede, Segurança com terminal e Recuperação passaram na VM de atualização. A coleta ocorreu após login autenticado, sem exceções de coleta na política instalada. Serviços, sockets, timers e paths de teste ficaram mascarados; autostart não executou. O firewall permaneceu ativo. A rede ficou desativada fora do modo com rede. Shift + Reiniciar no login mínimo abriu Recuperação.

A edição Servidor removeu 68 pacotes do desktop e reiniciou sem Plasma, com cerca de 587 MiB de RAM em repouso na VM de 4 GiB. Rede, serviços, recursos, firewall e controles de host abriram pelas cópias próprias da edição. Os botões padrão foram conferidos em português. A proteção APT e os certificados de firmware permanecem no componente comum.

O gerenciador de VMs listou as oito definições anteriores após autorização administrativa. Uma VM de teste adicional passou por criação UEFI/Secure Boot/TPM, início KVM, pausa, retomada, alteração de memória/CPU/adaptadores e restauração de checkpoint combinado. A definição de teste foi removida; as oito anteriores mantiveram seus hashes. A remoção e reinstalação do recurso de virtualização também preservou essas definições e terminou sem pendências no dpkg.

A prévia de remoção detectou tentativa do APT de substituir o QEMU amd64 por i386. A seleção foi completada com os componentes do hipervisor, e o backend passou a recusar planos de remoção que instalem substitutos. O inventário conserva identidades e tamanhos por arquitetura. Três testes novos passaram e a prévia real corrigida contém somente remoções.

Um adaptador WireGuard temporário validou a apresentação de dois IPv4, IPv6, máscaras e conectividade limitada. O teste não usou um servidor VPN externo e não comprova tráfego com pares remotos. A interface e o perfil de teste foram removidos.

A ISO source12 segue em compressão e não será publicada como final, pois a correção do plano de recursos entrou depois, na source13. O último ajuste local adicional prepara o teste de tradução para execução sem monitor. A compilação final deve usar a próxima fonte congelada.

## Candidata final source16

A fonte congelada source16 contém 726 arquivos; SHA256 do arquivo de fontes: `e3e2b51c5503450e79b4e329b58018b1d219a088110cab4e6d1de855582a22a3`. Os 21 pacotes foram gerados. A compilação completa está na compressão da ISO, ainda sem publicação final.

Os 76 scripts de regressão passaram sobre os componentes source16 na sessão live source12. Dois casos internos inicialmente pulados foram executados separadamente: 23 casos da plataforma com privilégios administrativos isolados e três casos de unidades com o helper nativo passaram. Propriedades nativas, KIO em barramento independente e estrutura dos pacotes passaram. Os controles reais de Wi-Fi, Bluetooth e áudio passaram com dispositivos simulados, com os estados restaurados; isso não substitui homologação física.

A guarda de remoção de compatibilidade Windows passou com processos reais wineserver32 e wineserver64. A edição Servidor manteve a criação automática de snapshots antes de uma atualização APT real. Evidências JSON e logs foram preservados. Continuam pendentes os ensaios finais de instalação, atualização e restauração com os artefatos source16, além do teste BIOS ao final.

## Instalação, recuperação e correção de vídeo

A ISO source16 compilou e passou nas verificações de estrutura. O Calamares concluiu uma instalação UEFI Desktop em disco virtual vazio de 40 GiB; a edição Servidor foi removida, o dpkg ficou limpo e o primeiro boot do disco instalado chegou ao kernel 6.12.115+deb13.1-amd64. O acesso SSH foi acrescentado somente como dependência de QA. A mídia Live Servidor também passou por login autenticado e console mínimo.

A restauração Timeshift da VM isolada retornou à base 0.8.5, preservando 1.793 hashes pessoais. A atualização HTTPS APT para source16 passou, com snapshot automático e novo boot. A regeneração real do menu GRUB e sua reversão após falha simulada passaram.

O ensaio de vídeo básico identificou tela preta com nomodeset em UEFI. A correção source17 conserva o framebuffer genérico, bloqueia os módulos dos fabricantes e força uma sessão X11 por software somente nessa inicialização. O login e o Plasma X11 reais passaram com LIBGL_ALWAYS_SOFTWARE=1 e KWIN_COMPOSE=N. Os seis testes novos e os nove testes de boot passaram em Linux. O diagnóstico iniciou com registro debug e removeu as configurações temporárias do vídeo básico.

A fonte source17 foi congelada com SHA256 `5897e8f66f6a450ab4a4c8c02200d8b60665472f96d0af19e4463ce2a5bed3ac`; a compilação completa está em andamento. A ISO source16 foi retirada por estar superada; nenhuma ISO 0.9 final foi publicada. A sincronização remota source16 preservou os 641 arquivos da base, conferiu 745 arquivos e manteve os demais arquivos do projeto. Ainda falta aplicar o delta source17 ao fim das validações.

## Conferência final de atualização — source18

A comparação dos arquivos após atualização identificou que Dolphin e KIO conservavam versões iguais às publicadas na 0.8.5. A atualização dos pacotes Linux BR havia passado, mas o APT não substituiu os oito pacotes nativos. A validação de atualização source17 fica incompleta para esse conjunto e não foi publicada.

A source18 incrementa Dolphin para +linuxbr2 e KIO para +linuxbr0.9.1. Drive Manager exige a nova revisão de Dolphin; Propriedades exige a revisão nova dos cinco componentes KIO. O README de apresentação passa a identificar a 0.9 e será incluído na nova compilação. A fonte congelada tem SHA256 `fed5eef1453318ccfb1ff0f64e9caa954b36c0c09e1aa1c2a50e58d711aac557`.

Os dois componentes nativos são recompilados em paralelo. O processo principal 3920487 está temporariamente retido por SIGSTOP antes da etapa completa de ISO, para garantir espaço livre. Os filhos de compilação continuam. Não retomar o processo sem conferir espaço e identidade.

A instalação UEFI Servidor source17 terminou: edição correta, 68 pacotes de desktop removidos e dpkg limpo. Sua raiz é 5b4ba7f8-e9d7-411a-9a80-d1fddeec11d1. Primeiro boot ainda pendente. As VMs e imagens publicadas foram preservadas. A limpeza de caches e duplicatas antigas não foi contabilizada como espaço liberado sem medição efetiva.

## Espaço e retomada da compilação final

Os dois boots instalados da candidata source17 foram preservados. O Servidor abriu o console autenticado, sem Plasma, com cerca de 600 MiB em uso na VM de 3 GiB; dpkg e unidades em falha ficaram limpos.

A compactação pelo próprio sistema de arquivos dos discos de teste desligados manteve cada arquivo byte a byte: hashes SHA256 antes e depois iguais. Os discos não foram removidos nem recriados. O espaço livre passou a cerca de 22 GiB. A compilação source18 foi retomada após essa conferência; os componentes Dolphin e KIO já foram recompilados nas novas revisões.

Ainda pendentes: conferência dos 21 pacotes source18, atualização natural a partir da 0.8.5 substituindo também os oito componentes nativos, ISO final, BIOS e publicação APT final. A publicação ativa continua na 0.8.5.


## Fechamento da Beta 1 — 5 de novembro de 2026

Fonte final source18. Compilação completa e verificações de estrutura aprovadas. A atualização natural da 0.8.5, solicitando apenas linuxbr-release, trouxe os oito pacotes nativos corrigidos; 1.500 arquivos instalados conferidos, snapshot criado e 1.793 arquivos pessoais preservados. Propriedades nativas passaram novamente após reiniciar. Desktop e Servidor instalados receberam o conjunto final: 1.500 e 916 arquivos conferidos, autenticação, dpkg limpo e nenhuma unidade com falha.

A ISO final iniciou por BIOS até o desktop e terminal. Por UEFI, iniciou em recuperação autenticada com rede inativa e firewalld ativo, depois voltou ao desktop normal com rede. Publicação APT 0.9-beta1 ativada na porta 8443 com as mesmas âncoras de confiança; manutenção executada e cliente baixou os 21 pacotes, conferindo todos os hashes. O catálogo público permanece na Hostinger.

Cópias de ISO, fontes e pacotes no disco D: verificadas por SHA256. Fontes do sistema e servidor sincronizadas com backups, 728 + 19 arquivos. As instalações limpas utilizaram mídias anteriores, seguidas da aplicação e validação dos pacotes finais; não se declara nova instalação completa da ISO source18 nem instalação BIOS. Consulte VALIDACAO-0.9-BETA1.md. VMs de testes desligadas; VM de uso e discos físicos preservados.
