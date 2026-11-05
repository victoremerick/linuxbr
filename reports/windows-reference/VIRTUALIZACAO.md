# Referência de gerenciamento de máquinas virtuais

Ambiente: Hyper-V no Windows 11 Enterprise Evaluation, dentro da VM de referência. A configuração foi exercitada com uma definição vazia e desligada. Não foi instalado nem inicializado um sistema nessa VM interna.

| Observação | Requisito para o Linux BR |
| --- | --- |
| Painel com lista, estado, uso, checkpoints, detalhes e ações por hospedeiro/VM. | Separar ações do computador e da VM selecionada, com estado real e métricas disponíveis. |
| Assistentes de criação rápida, criação, importação, disco e inspeção. | Assistentes gráficos, revisão das escolhas e diagnóstico de pré-condições. |
| Configurações após criação com hardware e gerenciamento. | Edição posterior com distinção entre alterações imediatas e dependentes de desligamento. |
| Firmware, segurança, processador, memória, controladores e discos. | Integrar libvirt, firmware, TPM e dispositivos suportados. Preservar configuração desconhecida ao editar. |
| Memória de início, mínima e máxima, reserva e prioridade. | Exibir somente mecanismos suportados; distinguir memória dinâmica, ballooning e limites do hospedeiro. |
| Discos com controlador/local, criar, editar, inspecionar e procurar. | Gerenciar anexos e conteúdo separadamente. Desanexar mantém o arquivo; excluir requer escolha e checagem de dependências. |
| Dois adaptadores associados a comutadores distintos. | Vários adaptadores por VM, cada um com rede, modelo, MAC e estado de conexão. |
| Adaptador com VLAN e controle de banda. | Configuração por interface, com validação de suporte à rede e ao backend. |
| Recursos avançados com MAC, proteção de DHCP/roteador e espelhamento. | Mapear a filtros, políticas e tipos de rede suportados, indicando limites. |
| Comutadores externo, interno e particular; intervalo global de MAC. | Oferecer NAT, redes isoladas/internas e ponte externa com explicação de acesso ao hospedeiro e à rede local. |
| Comutador com nome, observações, tipo e VLAN da interface de gerenciamento. | Editor de redes existentes e prévia do impacto sobre as VMs conectadas e o acesso remoto. |
| Árvore com serviços de integração, checkpoints e ações automáticas. | Integração do convidado, políticas de checkpoints e início/parada automáticos com condições claras. |
| Opções de mover e exportar no gerenciador. | Separar mover arquivos locais, exportar e migrar para outro hospedeiro; validar os destinos. |

Recursos adicionais de Windows Server, como replicação Hyper-V e migração ao vivo, não foram homologados no Windows cliente. Sua presença no planejamento exige mecanismo equivalente real, infraestrutura e validação próprias.

## Capturas

- [Painel e ações](capturas/09-hyperv-painel.png).
- [Memória após criação](capturas/10-hyperv-memoria.png).
- [Adaptador e VLAN](capturas/11-hyperv-adaptador.png).
- [Recursos avançados do adaptador](capturas/12-hyperv-rede-avancada.png).
- [Tipos de comutador](capturas/13-hyperv-tipos-rede.png).
- [Propriedades de rede existente](capturas/14-hyperv-rede-existente.png).

Fontes: [Hyper-V no Windows](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/hyper-v-overview?pivots=windows), [replicação](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/replication-overview), [redes libvirt](https://libvirt.org/formatnetwork.html) e [máquinas e dispositivos libvirt](https://libvirt.org/formatdomain.html).
