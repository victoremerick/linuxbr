# Linux BR 0.8.5 — requisitos e revisão de funcionalidades

Estado: planejamento e levantamento de referências, iniciado em 4 de novembro de 2026. Os itens deste documento não constituem uma versão implementada ou homologada. A distribuição publicada permanece 0.8 Beta 1.

## Objetivo

Completar os caminhos de configuração usados por quem vem do Windows, tornar a Loja Linux BR a entrada principal para aplicativos e oferecer administração gráfica de máquinas virtuais. A revisão inclui as páginas internas das Configurações, os diálogos relacionados e os estados sem hardware, sem conta ou sem conexão.

Cada página precisa ter localização previsível, pesquisa por termos brasileiros e sinônimos do Windows, título, descrição, ícone próprio, navegação de retorno e acesso às configurações relacionadas. Uma preferência deve refletir o estado efetivo do serviço. Alterações administrativas apresentam o alcance e usam autorização nativa. Botões sem implementação não contam como funcionalidades entregues.

## Configurações: cobertura exigida

A coluna Base identifica componentes existentes ou candidatos. Sua presença não significa que a experiência integrada esteja concluída. A cobertura precisa ser conferida por subpágina e por ação.

| Área | Páginas e detalhes a cobrir | Base e trabalho necessário |
| --- | --- | --- |
| Início | Busca, resumo do computador, conexões, armazenamento, atualizações, tarefas recentes e atalhos úteis. | Central Linux BR; mostrar estados locais, sem publicidade ou exigência de conta online. |
| Sistema — tela | Disposição de monitores, principal, resolução, orientação, escala por monitor, luz noturna, frequência, HDR e calibração quando suportados; ações para várias telas. | KScreen, KWin, módulos de cor; detectar capacidades reais, distinguir Wayland e X11. |
| Sistema — som | Saída e entrada padrão, dispositivos, teste, volume por aplicativo, perfis, balanço, permissões do microfone e resolução de problemas. | PipeWire, WirePlumber e módulo de áudio; preservar escolhas por dispositivo. |
| Sistema — notificações e foco | Avisos por aplicativo, sons, histórico, Não perturbe, exceções, horários e comportamento durante apresentação ou jogo. | Plasma; identificar lacunas de agendamento e regras automáticas antes de expor controles. |
| Sistema — energia | Tela e suspensão por fonte, tampa, botão de energia, perfis, bateria, consumo e condições que impedem suspensão. | PowerDevil; bateria e perfis aparecem conforme hardware e serviços. |
| Sistema — armazenamento | Volumes e letras de unidade, uso por categoria, temporários com prévia, limpeza, destino de novos arquivos, discos, montagem, integridade e criptografia. | Gerenciador de unidades, UDisks, Filelight; limpeza nunca inclui arquivos pessoais silenciosamente. |
| Sistema — janelas | Encaixe e layouts, organização de janelas, Alt+Tab, áreas de trabalho, restauração da sessão e preferências por aplicativo. | KWin e Plasma; integrar opções existentes, documentar diferenças de comportamento. |
| Sistema — compartilhamento e continuidade | Área de transferência e histórico, envio entre dispositivos, projeção, celular e compartilhamento nas proximidades. | Klipper, KDE Connect e serviços compatíveis; não anunciar protocolos ausentes como disponíveis. |
| Sistema — recuperação | Pontos de sistema, backup pessoal, reparo, inicialização avançada, logs e exportação de diagnóstico revisável. | Recuperação Linux BR, Timeshift, backup pessoal; distinguir restauração de sistema de arquivos pessoais. |
| Sistema — acesso remoto | Habilitação explícita, protocolos, usuários autorizados, endereço, firewall, sessão atual ou separada e diagnóstico de conexão. | KRdp e serviços suportados; recursos variam entre Wayland/X11. |
| Sistema — informações | Nome do computador, versão, arquitetura, CPU, memória, GPU, firmware, Secure Boot, TPM, suporte e cópia dos dados técnicos. | Página Sobre e KInfoCenter; não publicar identificadores pessoais no relatório padrão. |
| Bluetooth e dispositivos | Adicionar/remover, reconectar, bateria, áudio, impressoras e scanners, câmera, mouse, touchpad, teclado, caneta, toque, USB e reprodução automática. | BlueZ, CUPS, Skanpage, libinput, UDisks e módulos KDE. Páginas de câmera e USB precisam de estados reais e permissões. |
| Rede e Internet | Estado, propriedades da conexão, Wi-Fi e redes salvas, Ethernet, IPv4/IPv6, DNS, DHCP/manual, VPN, proxy/PAC, hotspot, modo avião, uso de dados, conexões limitadas e diagnóstico. | NetworkManager e integração existente. Proxy de KDE, navegador e outros aplicativos deve explicar o alcance. |
| Rede avançada | Vários adaptadores, ativação/desativação, prioridades, rotas, DNS por conexão, ponte, VLAN, compartilhamento, descoberta e unidades de rede. | NetworkManager e Samba; separar redes do hospedeiro das redes virtuais. Alterações que cortam acesso oferecem retorno e confirmação. |
| Personalização | Fundo, apresentação de slides, cores, claro/escuro, temas, ícones, cursores, fontes, bloqueio, menu Iniciar, barra de tarefas, bandeja, pastas visíveis e teclado virtual. | Plasma e página Aparência; prévia e restauração das escolhas. Iluminação dinâmica depende de dispositivo e serviço compatível. |
| Aplicativos | Instalados, tamanho e origem, remover, reparar quando suportado, dados e cache, padrões por extensão/protocolo, aplicativos de sites, inicialização, recursos opcionais e reprodução de vídeo. | Loja Linux BR, APT, Flatpak, MIME/KIO, Chromium e Wine. Nunca apresentar reparo ou restauração universal sem suporte do formato. |
| Contas | Dados do usuário, foto, contas locais, grupos, administrador/padrão, criação/remoção, senha, bloqueio, entrada automática, autenticação adicional e sessão. | AccountsService, PAM, SDDM e KWallet. Entrada automática explica exposição dos dados; biometria depende de hardware compatível. |
| Contas — organização e backup | Contas online, trabalho/escola, domínio, credenciais, backup de preferências, restauração e múltiplos usuários. | Integrações explicitamente suportadas; domínio Samba/AD não equivale a todos os serviços de identidade Microsoft. Não solicitar conta Microsoft para usar o sistema. |
| Hora e idioma | Relógio automático/manual, sincronização, fuso, idioma de exibição, pacotes, região, moeda/data/números, ABNT2, vários layouts, digitação, ortografia e fala. | timedatectl e módulos KDE. Português brasileiro deve permanecer padrão consistente em aplicativos e instalador. |
| Jogos | Biblioteca, ambientes Wine/Proton, dependências, controles, modo de desempenho, captura, áudio e diagnóstico por jogo. | Central Windows existente, Steam/Proton, GameMode e ferramentas disponíveis. Compatibilidade e antitrapaça são avaliados por jogo. |
| Acessibilidade — visão | Tamanho do texto, escala, efeitos/animações, contraste, filtros de cor, lupa, cursor de texto, ponteiro e leitor de tela. | KWin, Qt, AT-SPI e leitor compatível; validar teclado, foco, nomes acessíveis e alto contraste. |
| Acessibilidade — audição e interação | Áudio mono, avisos visuais, legendas quando disponíveis, teclas de aderência/lentas/repetição, teclado virtual, mouse pelo teclado, fala e dispositivos assistivos. | Módulos de acessibilidade e serviços compatíveis. Legenda ao vivo, ditado e controle ocular exigem avaliação separada. |
| Privacidade e segurança — proteção | Firewall, atualizações, criptografia, firmware, inicialização segura, integridade do sistema, bloqueio, credenciais e proteção de aplicativos. | Mecanismos nativos; não chamar um diagnóstico simples de proteção completa nem copiar indicadores de segurança sem verificação. |
| Privacidade — permissões | Câmera, microfone, localização, tela, notificações, contas, contatos, calendário, arquivos, pastas pessoais, dispositivos e execução em segundo plano. | Portais e permissões Flatpak/Chromium; aplicativos nativos sem isolamento não oferecem a mesma granularidade. Mostrar essa diferença por formato. |
| Privacidade — histórico | Arquivos recentes, indexação, histórico de pesquisa/área de transferência, diagnósticos, envio de dados e limpeza por categoria. | Baloo, KRunner, Klipper e serviços existentes; escolhas explícitas, efeitos descritos e coleta mínima. |
| Atualizações | Buscar, fila, progresso, histórico, falhas, reinício necessário, horários, atualização offline quando suportada, firmware, canais e fontes. | Atualizador Linux BR, repositório PHP, APT, Flatpak e fwupd; coordenar transações e evitar dois gerenciadores simultâneos. |
| Ferramentas relacionadas | Propriedades de arquivos e pastas, dispositivos, discos, serviços, eventos, tarefas agendadas, desempenho e Gerenciador de Tarefas. | Integrar os recursos existentes; ferramentas administrativas frequentes precisam de interface gráfica e diagnóstico exportável. |

### Comportamentos transversais

- Pesquisar também por termos como programas, desinstalar, painel de controle, resolução, som, impressora, senha, IP, rede, startup e restaurar.
- Permitir navegação integral por teclado, leitores de tela, ampliação e alto contraste; evitar truncar texto em português.
- Indicar valor atual, valor pendente, reinício necessário e erro recuperável. Cancelar uma edição não deve alterar o serviço.
- Explicar por que uma opção está ausente ou indisponível: dispositivo, driver, pacote, permissão, conexão ou sessão.
- Distinguir preferências por usuário das configurações do computador. Respeitar múltiplos usuários e sessões simultâneas.
- Oferecer páginas relacionadas e retorno ao mesmo ponto após abrir uma ferramenta auxiliar.
- Conferir persistência após reiniciar e comportamento de instalação limpa e atualização de versão.

### Diálogos e ferramentas além da página principal

A revisão também precisa acompanhar os links de configurações relacionadas. No Windows, parte das funções permanece em diálogos tradicionais; copiar somente o menu lateral deixaria lacunas importantes.

| Conjunto | Detalhes a verificar |
| --- | --- |
| Arquivos e pastas | Propriedades, seleção múltipla, ACL efetiva, herança, compartilhamento, metadados, versões anteriores, hash, compatibilidade, atalhos, itens ocultos e extensões. Preservar as integrações da 0.8. |
| Adaptadores | Endereços e prefixos, gateway, DNS, rotas, MTU, métricas, DNS por conexão, autenticação Wi-Fi, certificados, proxy, reconexão, economia de energia e limitações do driver. |
| Som e vídeo | Propriedades do dispositivo, canais, frequência/amostragem quando configurável, padrão de comunicação, atalhos de troca de saída, escala fracionada e múltiplos monitores com escalas diferentes. |
| Impressoras | Padrão, fila, pausar/retomar, cancelar trabalho, página de teste, propriedades, papel, cor, duplex, driver e impressora de rede. |
| Contas e credenciais | Troca de senha, expiração quando suportada, bloqueio, grupos, credenciais SMB, carteira e recuperação de acesso; preservar arquivos ao remover apenas uma conta. |
| Armazenamento | Montagem automática, rótulo e letra, remoção segura, somente leitura, SMART, TRIM, criptografia, chave de recuperação e volumes de rede. Formatação exige unidade e alcance identificados. |
| Administração | Serviços, inicialização, eventos/logs, agendamentos, variáveis de ambiente de usuário/sistema, nome do computador e domínio, sessões e opções avançadas de boot. |
| Aplicativos | Escolha de programa por tipo, alteração de protocolo, argumentos de atalho, pasta de trabalho, modo de compatibilidade por ambiente e resolução de falhas sem apagar dados automaticamente. |
| Internet e navegador | Downloads, padrões, perfis, cookies, certificados, permissões de sites, proxy e integração de webapps. Configuração do Chromium não deve ser apresentada como configuração de todo o sistema. |

Disponibilidade de recurso no Windows 10, no Windows 11, em edição cliente ou em Windows Server deve ser identificada no levantamento. Uma única VM não comprova cobertura de todas as versões nem de hardware ausente.

### Casos condicionais e avançados

- Rede móvel, modem e eSIM dependem de equipamento, operadora e integração adequada; usar ModemManager como candidato, sem declarar suporte antes de validar.
- Chaves de segurança, credenciais sem senha e biometria precisam de integração real de autenticação e recuperação de acesso. Não armazenar senhas em texto simples para imitar um fluxo de entrada.
- Thunderbolt/USB4, iluminação de periféricos, caneta e gestos avançados exigem detecção e política de autorização do dispositivo.
- Pools de armazenamento, RAID e volumes lógicos precisam de projeto e validação próprios. Identificar capacidades de LVM, mdadm e sistema de arquivos antes de expor criação ou recuperação.
- Preferências de desenvolvedor incluem terminal padrão, variáveis de ambiente, acesso remoto, extensões e componentes opcionais, com separação entre usuário e computador.
- Limites de banda, cache e fontes de atualização devem controlar os gerenciadores efetivamente usados. Serviços de distribuição específicos de outro sistema não recebem um controle meramente decorativo.
- Reparação, restauração de preferências e reinstalação devem explicar quais aplicativos, contas e arquivos serão preservados ou removidos e exigir destino e alcance identificados.

## Loja Linux BR

Substituir os caminhos da central que ainda abrem Discover, incluindo atualizações e firmware, somente quando o fluxo equivalente estiver funcional. Manter os serviços de instalação necessários; trocar a interface não exige remover todos os componentes compartilhados.

- Início com curadoria, categorias, pesquisa, filtros, favoritos e apresentação consistente, com ícones próprios e imagens quando disponíveis.
- Página do aplicativo com descrição, fornecedor, origem, formato, licença, arquitetura, tamanho conhecido, permissões, versão e requisitos. Distinguir programa Linux, webapp e programa Windows.
- Biblioteca com instalados e perfis web, ações abrir/remover, fila de downloads, progresso, cancelamento permitido, erros, histórico e atualizações.
- Configurações para fontes APT e Flatpak e catálogos web/Windows. Adicionar, editar, habilitar e remover com validação e indicação da confiança e do alcance. Uma fonte não suportada não recebe botão de instalação fictício.
- Programas Windows mostram nível de compatibilidade conhecido, ambiente escolhido e acesso à fonte oficial. Não executar automaticamente um instalador baixado.
- Webapps usam favicon, nome e domínio reconhecíveis. Uma conta salva abre diretamente; múltiplos perfis apresentam seleção central com abertura de um ou mais. Novo perfil inicia em janela e sessão separadas.
- Pesquisa unificada com alternativas nativas, sem confundir popularidade com compatibilidade ou segurança.

## Máquinas virtuais

Aplicação própria com libvirt/QEMU/KVM. A referência Hyper-V serve para tarefas e organização; recursos do Windows Server devem ser identificados separadamente dos recursos disponíveis no Windows cliente.

| Fluxo | Escopo |
| --- | --- |
| Painel | Lista, estado, pesquisa, CPU/memória/disco/rede, eventos, console, iniciar, reiniciar, desligar normalmente, desligar forçado e salvar estado com distinção clara. |
| Criação | Assistente com ISO, sistema, nome, localização, firmware, Secure Boot, TPM virtual, CPU, memória, disco e rede; modelos e revisão antes de criar. |
| Edição posterior | CPU/topologia, limites, memória dinâmica quando suportada, controladores, discos, ISO, ordem de boot, gráficos, vídeo, som, USB e dispositivos. Indicar quais mudanças exigem desligamento. |
| Rede | Adaptadores múltiplos, MAC, modelo, conexão/desconexão, NAT, rede isolada, rede interna e ponte externa; DHCP, DNS, sub-redes, VLAN e regras conforme backend. |
| Armazenamento | Criar/anexar/desanexar discos, formatos suportados, expansão, consulta de espaço real, pools e cadeia de dependências; compactação e conversão com pré-condições. |
| Estados e cópias | Checkpoints com/sem memória quando suportados, retorno, exclusão e árvore de dependências; clonagem, importação, exportação e backup consistente. Snapshot não substitui backup. |
| Hospedeiros | Conexão local e remota autenticada, permissões, caminhos e redes do hospedeiro correto; migração com checagem de CPU, armazenamento e conectividade. |
| Continuidade | Mapear replicação, failover e recuperação como funcionalidades adicionais. Só declarar operação quando o mecanismo real e os cenários de falha forem validados. |
| Preferências | Diretórios padrão, redes, dispositivos, atalhos, console, integração com convidado, início/desligamento automático, logs e diagnóstico. |

Exclusão distingue remover a definição e apagar discos. Mostrar caminhos, dependências e outras VMs que utilizam o arquivo. Não oferecer passagem direta de um disco físico como escolha padrão.

A observação do diálogo de rede do Hyper-V acrescenta à matriz: MAC dinâmico/estático, intervalo de MAC do hospedeiro, VLAN por adaptador e por rede de gerenciamento, limites de banda, proteção de DHCP e anúncios de roteador, controle de alteração de MAC e espelhamento de portas. Aceleração de rede, NUMA e compatibilidade de CPU precisam ser expostos conforme as capacidades efetivas do backend e do equipamento. Recursos de cluster não devem aparecer como funcionais em um único computador sem essa infraestrutura.

## Evidências e conclusão

A referência instalada é Windows 11 Enterprise Evaluation em português, com avaliação oficial de 90 dias, em disco virtual separado. O levantamento das telas está em `reports/windows-reference` no workspace de desenvolvimento. Páginas apenas citadas pela documentação precisam ser distinguidas das observadas nessa instalação.

Para concluir a 0.8.5: implementar os itens aprovados, manter matriz por subpágina com estado real, validar instalação limpa e atualização a partir da 0.8, testar operações e falhas em dados descartáveis, e reunir capturas e resultados. Disponibilidade de módulo KDE, execução de uma URI ou presença de botão não comprovam funcionamento completo.

Referências de navegação: [páginas de Configurações](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-settings), [Hyper-V no Windows](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/hyper-v-overview?pivots=windows), [replicação](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/replication-overview) e [avaliação oficial](https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise).

Bases técnicas para a implementação: [permissões e portais de aplicativos](https://docs.flatpak.org/en/latest/sandbox-permissions.html), [redes virtuais](https://libvirt.org/formatnetwork.html) e [configuração de máquinas e dispositivos](https://libvirt.org/formatdomain.html).
