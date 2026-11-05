# Máquinas virtuais no Linux BR 0.8.5

Abra **Máquinas virtuais** pelo menu, pelas Configurações ou pelo comando familiar `virtmgmt.msc` na janela Executar.

## Hospedeiro e autorização

**Este computador — administração** acessa as máquinas do serviço do sistema e solicita autorização administrativa nativa. **Minha conta** usa o serviço pessoal. Um servidor remoto usa SSH e libvirt; o servidor precisa ter esses serviços configurados e permitir o acesso da conta escolhida. A identidade do servidor deve ser conferida na primeira conexão. Senhas não são armazenadas nas preferências do gerenciador.

Uma conexão bem-sucedida é lembrada. Preferências de memória, processadores, disco, rede e local de armazenamento são separadas por hospedeiro e não alteram máquinas já criadas. Caminhos de ISO e discos sempre se referem ao hospedeiro selecionado.

## Criar e configurar

**Criar VM → Assistente completo** oferece a criação detalhada e a escolha de mídias e armazenamento em interface gráfica. **Criação rápida** mantém o formulário simplificado, com seleção local de ISO. Para uma VM existente, **Configurações → Avançado → Abrir editor gráfico completo** abre os controles de dispositivos e opções adicionais; a definição XML continua disponível para ajustes específicos. O assistente e o editor completos usam o virt-manager, integrado à conexão libvirt selecionada.

O assistente cria uma definição e um disco dinâmico novos; não escolhe discos físicos. Se não houver armazenamento configurado, permite criar um local padrão. O modelo Windows seleciona SATA, adaptador compatível, UEFI, Secure Boot e TPM 2.0. A ISO e a licença do convidado são fornecidas pelo usuário.

Depois de criar, selecione a máquina e abra **Configurações**. Há recursos, adaptadores, discos e mídias, checkpoints, firmware e dispositivos, inicialização e CPU. O editor avançado permite ajustes de topologia e dispositivos suportados pelo libvirt, preserva a identidade da VM e guarda a definição anterior. Alterações de hardware exigem desligamento e não são aplicadas sobre um estado salvo.

Novas VMs locais com Secure Boot usam um modelo que acrescenta as autoridades Microsoft de 2023 às chaves da base. Isso atende carregadores Windows assinados pela nova cadeia e preserva as autoridades e revogações existentes. As autoridades públicas são verificadas por SHA-256 e vêm do [repositório oficial em revisão fixa](https://github.com/microsoft/secureboot_objects/tree/3d762aecbaecd12402efd21ba89c8c7bd40da4bd). O certificado de plataforma PK não é substituído.

Para uma VM já criada, **Firmware e dispositivos → Atualizar certificados Secure Boot** opera com a VM desligada e cria um checkpoint combinado antes de alterar as variáveis. Guarde as chaves de recuperação de volumes criptografados. Esta ação acrescenta autoridades de confiança; não desativa Secure Boot nem muda sua preferência. Nesta edição, a atualização de uma VM existente exige variáveis no formato raw. Em um servidor remoto, a disponibilidade do modelo de novas VMs depende do firmware instalado naquele servidor.

O disco gravável de uma VM não pode ser anexado a outra pela interface comum. Discos base de cadeias gerenciadas também são protegidos. Desconectar um disco ou remover uma definição não apaga seus arquivos.

## Estado, checkpoints e cópias

- **Salvar estado** interrompe a execução e permite retomá-la pelo botão Iniciar. Não cria um histórico de versões.
- O checkpoint com a máquina desligada combina discos, variáveis de firmware e estado do TPM. Sua restauração confere a integridade das cópias e bloqueia a inicialização se a recuperação do estado não concluir.
- Checkpoints com memória são limitados, nesta edição, a BIOS sem TPM. O retorno à memória salva deixa a VM pausada para revisão. Em UEFI/TPM, use checkpoint desligado ou salvar estado.
- Checkpoints antigos que não incluam firmware/TPM são preservados, mas sua restauração não é executada por esta interface quando esses componentes forem necessários.
- **Exportar VM completa** cria uma nova pasta com discos, configuração, firmware, TPM e manifesto SHA-256. A VM deve permanecer desligada durante toda a cópia. Discos com base são consolidados quando o armazenamento e o formato permitem.
- **Importar VM completa** confere o manifesto e os arquivos, cria novos volumes e recusa substituir uma VM existente. A opção de nova identidade troca o UUID do hospedeiro e os endereços MAC. Arquivos, contas e a identidade interna do sistema convidado permanecem na cópia; a generalização do convidado é uma tarefa separada.
- **Clonar** usa a mesma cópia completa e as mesmas conferências. A cópia temporária exige espaço no computador que executa o gerenciador.
- Exportação de definição XML não inclui os discos. Sua importação avançada exige revisão explícita dos caminhos e dispositivos.

Cópias completas contêm dados privados e precisam de armazenamento protegido. Checkpoint não substitui backup em outro dispositivo.

## Redes e armazenamento

Redes NAT permitem saída pelo hospedeiro; redes internas ligam VMs e hospedeiro; redes privadas ligam somente as VMs; a ligação externa usa uma ponte previamente existente. A interface não transforma automaticamente o adaptador físico usado pelo acesso remoto em uma ponte.

Cada VM pode ter vários adaptadores, com modelo, MAC, conexão do cabo, VLAN de ponte e limite de banda. As redes internas/NAT incluem sub-rede IPv4 e DHCP; reservas existentes compatíveis são preservadas na edição. A rede do hospedeiro continua nas Configurações de Rede do sistema.

Locais de armazenamento podem ser criados, ativados, desativados e lembrados no início. Volumes podem ser criados, conectados, consultados e expandidos. Expandir o volume não expande automaticamente a partição e o sistema de arquivos do convidado.

## Migração e continuidade

O comando Migrar usa a API nativa do libvirt, com armazenamento compartilhado e validação de compatibilidade do backend. Uma migração concluída de uma VM persistente mantém a definição no destino e remove a definição da origem. O procedimento exige outro hospedeiro configurado e sua homologação é separada dos testes locais.

Esta edição não oferece replicação contínua, cluster ou failover automático. Cópias completas permitem recuperação manual. Alta disponibilidade depende de infraestrutura adicional e não é anunciada como proteção ativa neste gerenciador.
