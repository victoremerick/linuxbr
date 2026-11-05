# Ambiente Windows e revisão para o Linux BR 0.8.5

Em 4 de novembro de 2026, foi instalado Windows 11 Enterprise Evaluation em português em uma máquina virtual separada no computador remoto. A avaliação oficial é de 90 dias. O instalador foi conferido por tamanho e SHA-256 antes do uso.

## Resultado da instalação

- Windows 11 Enterprise Evaluation 26H2, versão 10.0.26300.9457, x64.
- Conta local de referência, idioma português brasileiro e fuso de Brasília.
- Quatro processadores virtuais, 8 GiB de memória e disco virtual de 96 GiB com alocação dinâmica.
- UEFI com Secure Boot ativo e TPM virtual presente e pronto.
- Licença de avaliação com estado de ativação válido na conferência inicial.
- Rede NAT; consoles restritos ao hospedeiro, sem publicar acesso remoto na rede local.
- Atalho **Windows 11 — Referência** na área de trabalho do computador remoto.

Os resultados estão em [conferência inicial](baseline-facts.json) e [integridade do instalador](download-verification.json). O primeiro ensaio de instalação falhou por nome de computador acima do limite; foi substituído por instalação limpa com nome válido. O [registro da tentativa](setup-attempt-01.json) preserva esse resultado.

## Revisão das Configurações

Foram consultadas 182 rotas de Configurações, com coleta dos títulos e controles no início e no fim da rolagem. O índice público contém 181 rotas e 125 trilhas distintas de títulos, após separar os balões de ajuda. Não houve falha de consulta na coleta final. Há rotas que apontam para a mesma página ou redirecionam conforme a edição e os dispositivos presentes.

Veja o [índice por página](CONFIGURACOES.md) e o [registro estruturado](settings-review.json). A consulta cobriu contas, aplicativos, dispositivos, acessibilidade, jogos, rede, personalização, privacidade, som, sistema, idioma e atualização. Isso não significa que todos os controles foram acionados ou que todos os diálogos foram investigados.

O [planejamento da 0.8.5](ESCOPO-0.8.5.md) organiza os equivalentes, as lacunas e os serviços candidatos no Linux BR. Inclui também diálogos tradicionais, configurações avançadas, estados sem hardware, permissões por formato de aplicativo, uma Loja própria e gerenciamento gráfico de VMs. A presença dos módulos KDE foi consultada na VM Linux BR existente: [inventário](linuxbr-modules.json).

O mesmo planejamento está registrado em `docs/VERSAO-0.8.5.md` no projeto e vinculado no README, separado do histórico de versões lançadas.

## Capturas conferidas

- [Configurações de tela](capturas/02-configuracoes-tela.png).
- [Aplicativos padrão](capturas/03-aplicativos-padrao.png).
- [Início da loja](capturas/04-loja-inicio.png).
- [Configurações avançadas de rede](capturas/05-rede-avancada.png).
- [Barra de tarefas](capturas/06-barra-de-tarefas.png).
- [Permissões da câmera](capturas/07-permissoes-camera.png).
- [Opções avançadas de atualização](capturas/08-atualizacoes-avancadas.png).

## Referência de virtualização

O Hyper-V foi ativado e o Windows reiniciado. O serviço de gerenciamento está em execução. Foi criada somente uma definição de VM vazia de geração 2, desligada, com dois processadores, memória dinâmica de 512 MiB a 2 GiB com início em 1 GiB, disco dinâmico de 16 GiB, Secure Boot e TPM virtual.

Foram criadas redes interna e privada e anexados dois adaptadores. A rede externa foi apenas observada na interface. O Fedora não recebeu ponte de rede ou alterações de seus adaptadores. A VM vazia não foi inicializada; não há evidência de desempenho ou de execução de um sistema aninhado.

Foram observados o painel do gerenciador, a árvore de configurações após criação, memória, propriedades de disco, adaptador, recursos avançados de rede e tipos/propriedades de comutadores. Veja a [conferência estruturada](hyperv-reference.json) e o [mapeamento funcional](VIRTUALIZACAO.md).

## Preservação e limites

Foram removidos somente quatro discos virtuais antigos autorizados, após verificar dependências e uso por processos. Os discos das VMs ativas, o Fedora, os discos físicos e os artefatos publicados da 0.8 foram preservados. Um checkpoint do novo Windows foi criado antes da ativação do Hyper-V, com cópia privada do estado de firmware e TPM.

Ao terminar, o Windows foi desligado normalmente e seu disco virtual passou pela verificação offline sem erros. As duas VMs Linux que estavam ativas continuaram em execução. Os inibidores temporários criados para este levantamento foram liberados, sem alterar preferências persistentes do hospedeiro. O servidor local de atualizações permaneceu ativo. Veja o [estado final](final-state.json). O Windows pode ser aberto novamente pelo atalho na área de trabalho do remoto.

Windows 10 e Windows Server não foram instalados. A VM não permite homologar dispositivos físicos ausentes. Recursos exclusivos de serviços externos e funcionalidades de servidor precisam de tratamento separado. Os controles de privacidade de Flatpak, Chromium e aplicativos nativos têm alcances diferentes, conforme seus mecanismos reais.

**A 0.8.5 permanece em planejamento.** Esta entrega prepara a referência e registra o escopo; não é uma nova ISO nem uma homologação das funcionalidades propostas.

Fontes técnicas: [avaliação oficial](https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise), [navegação das Configurações](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-settings), [Hyper-V](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/hyper-v-overview?pivots=windows), [permissões Flatpak](https://docs.flatpak.org/en/latest/sandbox-permissions.html) e [redes libvirt](https://libvirt.org/formatnetwork.html).
