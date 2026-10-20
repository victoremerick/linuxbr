# Central do Sistema: rede, segurança, áudio e tarefas

Esta entrega amplia a Central sem substituir os serviços do Linux. As novas páginas aparecem na navegação e na busca; as configurações avançadas do KDE continuam disponíveis quando uma opção ainda não foi incorporada à Central.

## Firewall

A página **Firewall** consulta o firewalld, mostra as zonas padrão e ativas, serviços, portas explícitas, regras avançadas e redirecionamentos. A aba **Aplicações com portas abertas** mostra os processos de escuta que `ss` consegue identificar para a sessão. A página permite ativar ou desativar o firewalld e liberar ou remover portas TCP/UDP persistentes, com autenticação administrativa. Uma regra de porta ou serviço se aplica à zona de rede; ela não concede acesso exclusivo a um executável. Alguns processos de outros usuários não têm nome visível sem privilégios elevados.

## Usuários e grupos

Em **Usuários → Grupos**, é possível criar e excluir grupos locais, adicionar e remover membros. As alterações usam `groupadd`, `groupdel` e `gpasswd` sob polkit. Grupos de sistema são protegidos; a última conta administrativa local não pode ser retirada de `sudo`. Grupos de Active Directory permanecem administrados pelo domínio.

## Rede e áudio

**Rede → Endereços IP e DNS** lista perfis Ethernet/Wi-Fi do NetworkManager e permite DHCP/SLAAC ou endereços manuais IPv4/IPv6, gateway e servidores DNS. A página valida endereços antes de salvar; a conexão deve ser reconectada para aplicar mudanças. Configurações avançadas de VPN e Wi-Fi continuam acessíveis pela Central através do módulo nativo do KDE.

**Áudio** lista saídas e microfones, define os padrões e permite escolher perfis oferecidos pela placa. O mixer mostra fluxos ativos por aplicativo, regula o volume de reprodução e move fluxos de reprodução ou captura para outro dispositivo. Ele usa `pactl` com PipeWire/PulseAudio; aplicativos sem fluxo ativo não aparecem. A persistência de rota entre sessões depende da política do WirePlumber.

## Iniciar e tarefas

O clique direito no botão Iniciar exibe ações do sistema no menu nativo do Plasma, incluindo **Executar**, Central do Sistema, rede, discos, firewall, terminal e **Gerenciador de Tarefas**. Executar abre caminhos ou programas sem invocar um shell. O Gerenciador de Tarefas mostra processos e uso de CPU/memória e pode enviar SIGTERM aos processos da própria conta, mediante confirmação.

## Validação

Execute `python3 tests/test-control-center-services.py` e `python3 tests/test-plasma-layout.py`. Para validar o menu e o diálogo Executar em uma ISO existente, use `python3 tests/settings-vm-smoke.py` e teste o clique direito no botão Iniciar. Recompile a ISO para incorporar as alterações à imagem distribuída; o teste em VM com sobreposição não altera a ISO anterior.
