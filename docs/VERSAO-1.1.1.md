# Linux BR 1.1.1

## Wiki integrada ao Desktop

A **Wiki do Linux BR** abre pelo menu Iniciar e por **Primeiros passos** e funciona offline. No Desktop, **F1** abre a ajuda no Explorador, nas Configurações e na Loja. As Configurações e a Loja também oferecem um botão **Ajuda**. O site publica os mesmos guias em [Wiki do Linux BR](https://linuxbr.homedeveloper.com.br/wiki/).

Os guias iniciais cobrem tarefas de uso diário, incluindo o Explorador, a Loja, aplicativos web, programas Windows, configurações, rede, recuperação e máquinas virtuais. No VM Server, digite `? N` para ver a ajuda da opção numerada ou `? termo` para pesquisar. No terminal, `linuxbr-console --ajuda termo` faz a mesma pesquisa.

Cada guia tem uma página própria e usa capturas do Linux BR com dados de demonstração. Ao adicionar ou alterar um recurso, atualize sua página em `usr/share/linuxbr/wiki/guias` no pacote `linuxbr-system` e a entrada no índice. Registre o nome usado no menu, o caminho até o recurso, os passos de uso e as condições que afetam sua disponibilidade. Preserve o nome do arquivo quando o título mudar para manter os links existentes.

## Ampliação do escopo

| Item | Entrega no código |
| --- | --- |
| 41 | Renomear em lote pelo Explorador, com prévia, data, numeração e detecção de colisões. |
| 59 | Identificação da versão nos guias e histórico de mudanças nas telas da wiki. |
| 62 | Seleção de origens e revisão de uma fila de instalações antes de iniciar as transações. |
| 81 | Diagnóstico com etapas de conexão, IP, gateway, DNS e conectividade. |
| 84 | Identificação de rede com portal e botão para abrir o navegador. |
| 86 | Prévia de câmera e medidor do microfone em Configurações. |
| 90 | Relatório de capacidade, ciclos e variação desde a primeira leitura registrada. |
| 94 | Ação do Explorador para listar processos consultáveis que usam o item ou a unidade. |
| 111 | Consulta offline da ajuda no console do VM Server, por número ou termo. |

O restante dos itens 41–120 e a homologação da ampliação seguem pendentes. A publicação da ISO e a atualização do notebook vêm após a conclusão e validação do conjunto.

## Mídia dedicada Linux BR VM Server

A ISO principal instala diretamente o Linux BR Desktop. O Linux BR VM Server tem sua própria ISO e um instalador identificado para essa edição. A mídia inclui QEMU/KVM, libvirt e a sessão gráfica mínima.

Após o login no VM Server, a sessão abre duas janelas sobre fundo preto. O terminal Bash fica atrás e a janela **Configuração do servidor** abre em primeiro plano com fundo grafite, texto branco, cursor amarelo-claro e menu numerado em português. **Alt+Tab** alterna entre elas. **Ctrl+Alt+C** reabre a configuração e **Ctrl+Alt+T** abre um terminal. O comando `linuxbr-console` também abre o menu no console de texto.

Digite `terminal` em uma janela Bash para abrir outra janela independente e voltar imediatamente ao prompt. Repita o comando para abrir mais janelas. Cada uma mantém seu próprio diretório de trabalho. Fechar as janelas iniciais mantém a sessão disponível para abrir novas janelas com **Ctrl+Alt+T**.

### Console do VM Server

- Configurar nome do computador, interfaces, IP, DNS, gateway, data, hora e fuso.
- Administrar contas, grupos, serviços, tarefas, firewall e armazenamento.
- Consultar atualizações, eventos e diagnósticos, além de abrir o terminal, reiniciar ou desligar.
- Habilitar acesso remoto pelo menu com autorização administrativa. Uma alteração de rede iniciada remotamente deve reverter se a conexão cair e a mudança ficar sem confirmação.

### Servidor de Máquinas Virtuais

O perfil instala QEMU/KVM e libvirt e inclui a administração de VMs no menu do primeiro login. O console deve mostrar o estado da aceleração por hardware e orientar o administrador se ela estiver desabilitada no firmware.

- Preparar o armazenamento e a rede das VMs, incluindo redes isoladas, NAT e ponte.
- Criar VMs com CPU, memória, discos e mídia de instalação. Alterar esses recursos após a criação.
- Listar VMs, ligar, desligar, reiniciar e escolher quais iniciam com o host.
- Oferecer console da VM, checkpoints, importação e exportação.
- Permitir que outro computador com Linux BR administre o host pela Central de Administração Remota, quando o administrador habilitar o acesso e delegar as permissões.

### Critérios de aceite

- Instalar a partir de cada ISO e confirmar que a mídia define sua edição. No VM Server, conferir o menu após a autenticação e reabri-lo a partir do Bash.
- Configurar a rede e um serviço pelo console, reiniciar e conferir a persistência das configurações.
- Criar, iniciar e reconfigurar uma VM no perfil dedicado. Confirmar a inicialização automática da VM após o reinício do host.
- Usar um segundo Linux BR para consultar e operar a VM com uma conta autorizada. Conferir que essa conta respeita as permissões delegadas.

### Validação no notebook de testes

O comando `linuxbr-console` foi instalado sobre o Linux BR 1.0 RC 2. A seleção dos dois perfis foi ensaiada em um ambiente isolado no próprio notebook. O teste no QEMU/KVM criou e iniciou uma VM UEFI sem mídia, mudou a memória para 768 MiB e a CPU para dois núcleos, habilitou o início automático e criou e restaurou um checkpoint. O console também criou um local de armazenamento e uma rede virtual isolada. A VM, o disco, o checkpoint e a rede de teste foram removidos depois do ensaio.

A instalação limpa pelo Calamares, o primeiro login após o boot do perfil dedicado e a administração por outro Linux BR seguem como critérios de aceite. A integração inicial com KDE Connect adiciona o atalho **Dispositivos conectados** e o envio de arquivos pelo menu de contexto. O pareamento e a entrega entre dois PCs precisam de validação ponta a ponta.

## Integração entre computadores com Linux BR

1. **Parear computadores na rede local.** Encontrar outros PCs com Linux BR e confirmar a conexão com um código exibido nas duas telas.
2. **Enviar arquivos pelo menu de contexto.** Escolher **Enviar para outro PC**, aguardar a aceitação do destinatário e acompanhar o progresso.
3. **Enviar links para outro computador.** Enviar uma página do navegador para abrir no outro PC, com a opção de guardar o link para depois.
4. **Compartilhar a área de transferência.** Enviar texto copiado manualmente para outro PC pareado e oferecer sincronização automática como opção.
5. **Sincronizar pastas escolhidas.** Manter pastas selecionadas em dois PCs e preservar as duas cópias quando houver edições conflitantes.
6. **Acessar pastas compartilhadas pelo Explorador.** Mostrar os computadores na seção **Rede** e permitir que o dono da pasta conceda acesso de leitura ou edição.
7. **Reinstalar aplicativos de outro PC pela Loja.** Importar a lista de um computador pareado, revisar os aplicativos e escolher entre os formatos testados no Linux BR.
8. **Levar preferências para outro computador.** Escolher quais temas, favoritos do menu Iniciar, atalhos e opções de acessibilidade serão importados.
9. **Sincronizar atalhos de webapps.** Mostrar os mesmos atalhos no menu Iniciar dos PCs pareados, com sessões de login independentes em cada computador.
10. **Continuar um trabalho em outro PC.** Mostrar documentos recentes das pastas sincronizadas e abrir o mesmo arquivo no outro computador.
11. **Compartilhar impressoras.** Usar uma impressora USB conectada a outro PC da rede e acompanhar a fila de impressão.
12. **Enviar digitalizações para outro PC.** Digitalizar no computador conectado ao scanner e entregar o PDF em uma pasta autorizada de outro PC.
13. **Usar um teclado e mouse em dois computadores.** Passar o cursor pela borda da tela para operar o outro PC e voltar com um atalho.
14. **Usar o notebook como segunda tela.** Estender a área de trabalho do desktop para o notebook pela rede ou espelhar a imagem.
15. **Prestar assistência remota.** Pedir ajuda a outro usuário e escolher se ele pode apenas ver a tela ou também controlar a sessão.
16. **Enviar diagnósticos ao computador de suporte.** Revisar o relatório na Central de Diagnóstico antes do envio a um PC pareado e registrar o que foi compartilhado.
17. **Fazer backup em outro computador.** Guardar versões anteriores dos arquivos em outro PC da rede e restaurar documentos ou pastas pela interface.
18. **Reaproveitar downloads de atualizações.** Usar um PC da rede como cache de pacotes APT e verificar as assinaturas em cada computador antes de instalar.
19. **Acompanhar a frota em um painel local.** Consultar a versão do Linux BR, o espaço disponível, as atualizações pendentes e o último contato dos computadores cadastrados.
20. **Coordenar atualizações em ondas.** Aplicar um lote primeiro ao PC piloto, conferir o resultado e liberar o mesmo lote para os demais dentro da janela de manutenção.

## Central de Administração Remota

A Central deve permitir cadastrar computadores autorizados, administrar o host e operar suas máquinas virtuais com permissões delegadas. O perfil **Servidor de Máquinas Virtuais** deve oferecer o menu local pelo terminal e permitir a administração de outro Linux BR pela Central.

21. **Configurar o host de virtualização.** Ativar o serviço e definir os locais padrão para VMs, discos e imagens ISO.
22. **Criar VMs em outro computador.** Escolher o host, CPU, memória, disco e mídia de instalação pelo assistente.
23. **Alterar uma VM existente.** Ajustar CPU, memória, firmware, ordem de boot e dispositivos, indicando quando é preciso desligar a VM.
24. **Controlar o estado das VMs.** Ligar, pausar, retomar, reiniciar, desligar e selecionar quais iniciam automaticamente com o host.
25. **Abrir o console da VM.** Acompanhar o boot, operar o instalador e recuperar a VM mesmo quando ela está sem rede.
26. **Gerenciar redes virtuais.** Criar redes isoladas, NAT ou em ponte e conectar cada adaptador virtual à rede escolhida.
27. **Administrar discos virtuais.** Criar, conectar e expandir discos, conferindo o espaço disponível antes de aplicar a mudança.
28. **Criar e restaurar checkpoints.** Registrar o estado de uma VM antes de uma mudança e selecionar um ponto para restaurar.
29. **Importar, exportar e clonar VMs.** Copiar uma VM para outro host ou usar uma VM existente como modelo.
30. **Migrar VMs entre hosts.** Mover a VM e seus discos para outro computador, com migração em funcionamento quando os hosts forem compatíveis.
31. **Replicar VMs para contingência.** Manter uma cópia em outro host e testar a ativação da réplica em uma rede isolada.
32. **Gerenciar serviços do sistema.** Iniciar, parar, reiniciar e configurar a inicialização automática de serviços como Samba, impressão e virtualização.
33. **Instalar funções do servidor.** Ativar funções como servidor de arquivos, impressão ou contêineres e acompanhar a instalação das dependências.
34. **Consultar eventos e logs.** Filtrar por serviço, gravidade e horário para investigar falhas do host e das VMs.
35. **Agendar tarefas.** Programar backups, manutenção e rotinas administrativas e consultar o histórico de execuções.
36. **Administrar usuários e grupos locais.** Criar contas e delegar permissões específicas, como operar VMs sem acesso à configuração do host.
37. **Configurar rede e firewall.** Alterar IP, DNS e regras de acesso, com reversão automática se uma mudança ficar sem confirmação após a perda da conexão administrativa.
38. **Gerenciar armazenamento do host.** Consultar discos, volumes e pontos de montagem e preparar um volume para VMs ou backups.
39. **Administrar certificados.** Importar e substituir certificados e consultar validade e serviços dependentes.
40. **Gerenciar DNS e DHCP da rede.** Criar nomes internos e reservas de IP para servidores e VMs.

## Estado da implementação

| Itens | Entrega disponível e pendência |
| --- | --- |
| 1–4 | KDE Connect oferece descoberta, pareamento e compartilhamento. O Explorador oferece envio direto e envio com aceite em duas etapas. **Links recebidos** permite guardar um link para depois. A área de transferência usa as preferências por dispositivo do KDE Connect. Falta ensaiar o recebimento e o aceite entre dois PCs. |
| 5–7 | Sincronização opcional com Syncthing, compartilhamento SMB existente e abertura de listas recebidas na Loja para revisar a reinstalação. A validação entre dois computadores segue pendente. |
| 8–10 | Personalização transfere cores e aplicativos fixados no Iniciar. Acessibilidade transfere ajustes de interação por teclado. Aplicativos web oferecem sincronização de atalhos públicos por pasta privada. **Continuar documento em outro computador** lista itens recentes de uma pasta sincronizada e envia um atalho relativo para revisão no destino. |
| 11–15 | O sistema oferece CUPS, digitalização e assistência por compartilhamento de tela. **Digitalizar e enviar** mostra uma prévia e envia o PDF salvo ao dispositivo escolhido. Deskflow compartilha teclado e mouse. A segunda tela combina um monitor virtual Plasma Wayland com um túnel SSH. A homologação dessas funções com equipamentos e sessões reais segue pendente. |
| 16–20 | A Central de Diagnóstico registra data, destinatário e categorias das solicitações entregues ao KDE Connect. **Backup em outro computador** cria versões criptografadas via SFTP e recupera arquivos em uma pasta nova. O console oferece cache para repositórios HTTP. Inventário e ondas fazem parte do serviço da organização. A confirmação de recebimento do diagnóstico entre dois PCs segue pendente. |
| 21–30 | O gerenciador libvirt cobre operações locais e remotas. A migração desligada copia os discos, mantém a identidade da VM e só tenta retirar a definição de origem após a importação. Os discos originais ficam guardados. A migração ao vivo oferece cópia de discos de arquivo independentes quando os hospedeiros estão preparados para migração TLS. Falta homologar com dois hospedeiros. |
| 31 | O gerenciador cria gerações de réplica offline em outro host, por solicitação ou pelo agendador da conta. A ativação de teste revalida a rede isolada. O agendamento exige SSH sem interação, espaço no destino e origem desligada. Falta o ensaio completo entre hospedeiros. |
| 32–38 | Cockpit cobre serviços, registros, contas, firewall e armazenamento. O console administra tarefas e consulta seu histórico. A conta de operador pode receber ações de energia para VMs específicas por SSH. O checkpoint do NetworkManager reverte alterações de rede. O firewall restaura regras de portas sem confirmação. Uma VM de laboratório confirmou o prazo de reversão e os limites da delegação. |
| 39–40 | O console consulta certificados e instala ou substitui a cadeia HTTPS do Cockpit, preservando a revisão anterior. O gerenciador libvirt administra nomes DNS e reservas DHCP das redes virtuais IPv4. O serviço opcional de LAN permite configurar resolução local, faixa DHCPv4 e reservas numa interface física com IPv4 estático. A atribuição de endereços a clientes físicos requer validação na rede de laboratório. |

## Usar o backup pela rede

1. No computador de destino, disponibilize SFTP para uma conta autorizada e reserve uma pasta gravável para o repositório.
2. No computador de origem, confirme a identidade do servidor SSH e configure o acesso por chave. O backup usa as chaves e os servidores conhecidos da conta.
3. Ative **Backup em outro computador** em **Recursos opcionais**. Abra **Backup e recuperação → Meus arquivos → Backup em outro computador**.
4. Informe o computador, o usuário SSH, a porta e o caminho absoluto da pasta remota. Crie o repositório uma vez e guarde a senha de criptografia.
5. Para restaurar, liste as versões e use o identificador da cópia. Informe o caminho original completo de um arquivo ou pasta, ou deixe o campo em branco para recuperar a versão inteira. Os dados são gravados em uma pasta nova no destino selecionado.

## Preparar uma segunda tela

1. No computador que terá a área de trabalho estendida, abra uma sessão Plasma Wayland e ative **Segunda tela pela rede** em **Recursos opcionais**. Configure o acesso SSH para a própria conta gráfica.
2. Abra **Segunda tela pela rede**, escolha **Criar tela para outro computador** e selecione a resolução. Deixe a janela aberta para manter o monitor ativo.
3. No outro Linux BR, reconheça previamente a chave do servidor SSH e configure o acesso por chave. Abra a opção **Conectar a uma tela** e informe a conta, a porta e o soquete exibido. Informe ao KRDC o código da sessão.
4. Organize o monitor na página **Telas** do computador que está compartilhando a área de trabalho.

## Administração do servidor

- Use **Delegar ações de energia de uma VM** com uma conta SSH dedicada, sem permissões administrativas próprias. A concessão é por UUID e inclui estado, inicialização, desligamento, reinício, pausa e retomada. Revogue a concessão antes de reaproveitar uma conta ou um UUID.
- Em **Regras de portas do firewall**, confirme pelo console em até dois minutos depois de testar uma segunda conexão. Durante esse período a regra anterior segue gravada no firewalld.
- Em **DNS e DHCP da rede local**, configure os registros e confira a interface e a faixa antes de ativar. Mantenha um único servidor DHCP por segmento. Para aplicar uma edição, use **Ativar** durante a manutenção.
- Em **Instalar certificado HTTPS do Cockpit**, revise o nome de acesso, a impressão digital e as datas. A nova cadeia entra em uso quando a Central é reiniciada. O navegador precisa confiar na autoridade que assinou o certificado.

## Evidências desta revisão

- Atualização por pacotes concluída em uma VM UEFI com resolução de 1280 × 768. A auditoria do dpkg terminou sem pendências.
- O KWin criou uma tela virtual. O soquete privado respondeu com RFB 3.8 e o protocolo também respondeu pelo túnel SSH.
- A regra temporária ficou ativa sem alterar a regra permanente e foi removida pelo agendador do host após o prazo.
- A conta de operador consultou a VM autorizada. O acesso a outro UUID, a execução de um comando administrativo arbitrário e o acesso depois da revogação foram negados.
- O DNS respondeu com o IPv4 configurado. Um cliente DHCPv4 recebeu o IP reservado para seu MAC numa rede isolada de laboratório.
- O Cockpit confirmou a instalação e a renovação da cadeia TLS. Um nome de acesso incorreto, uma chave que não correspondia ao certificado e uma falha do seletor foram rejeitados.
- Os favoritos foram incluídos pelo serviço de atividades do KDE e exportados na VM. O scanner virtual SANE gerou um PDF de uma página.
- Um disco de teste foi exportado e reimportado para outro pool pelo libvirt, com conteúdo e UUID conferidos. O agendador disparou e removeu uma tarefa no systemd da VM.

### Notebook físico

- Atualização da 1.0 RC 2 para `1.1.0~alpha1` com os pacotes que incluem as funcionalidades em desenvolvimento da 1.1.1. O APT atualizou 16 pacotes, instalou 1 e não removeu nenhum. A auditoria do dpkg e a sintaxe da configuração GRUB passaram. O snapshot Btrfs de recuperação é `@pre-linuxbr-111-20261113-224534`.
- Passaram no notebook a montagem das telas de recuperação e favoritos, o histórico de diagnóstico, a importação de preferências em perfil temporário, os arquivos de link e continuidade, a sincronização de atalhos web e a digitalização em PDF com o scanner virtual SANE.
- O agendador executou uma tarefa real e o firewall reverteu a regra temporária. A delegação limitou o acesso a uma VM e foi revogada. Uma VM de teste preservou UUID e conteúdo do disco ao trocar de pool. Um cliente recebeu a reserva DHCPv4 em rede isolada.
- A criação da segunda tela funcionou na sessão Wayland, com resposta RFB pelo soquete privado. O túnel SSH para esse soquete falhou no notebook e também falhou com um soquete de teste independente.
- A instalação e renovação do certificado e a restauração de backup passaram em diretórios temporários usando Cockpit e Restic. O backup desse ensaio usou um repositório local. Ficaram pendentes o reinício após a atualização, o teste SFTP no notebook e os fluxos que precisam de outro computador pareado ou hospedeiro.

### Retomada da homologação

- A suíte de integração passou com 58 testes. A suíte complementar de firmware, virtualização e plataforma passou com 23 testes no laboratório.
- O notebook deixou de responder no endereço SSH conhecido. O PiKVM estava acessível e indicou entrada HDMI inativa. O notebook não tem ligação ATX com o PiKVM e precisa ser ligado ou despertado localmente para retomar a homologação.
- O diário do kernel confirmou suspensão `s2idle` e retorno à sessão anterior. Quando o console voltou mas a rede não respondeu, a reconexão do Wi-Fi pelo console físico restabeleceu o SSH no mesmo endereço. Durante a homologação, foi aplicado um bloqueio temporário de suspensão.
- O Restic passou no notebook com OpenSSH/SFTP temporário em loopback, verificação da chave do servidor, duas versões e restauração seletiva. A validação pela LAN com outro servidor permanece aberta.
- O encaminhamento SSH do soquete Unix falhou pela LAN com clientes Linux e Windows e com um soquete de teste independente do KWin. O mesmo tipo de encaminhamento funcionou com um servidor SSH temporário em loopback.
- Permanecem pendentes o boot UEFI e a sessão Wayland após reiniciar, a segunda tela via SSH pela LAN, o envio e recebimento pelo KDE Connect, a migração ao vivo e a réplica agendada entre hospedeiros.
