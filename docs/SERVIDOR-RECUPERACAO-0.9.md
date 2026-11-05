# Sessão Servidor e recuperação

A edição Servidor usa X11, Openbox e o console de configuração do Linux BR. O Plasma completo não inicia. A autenticação continua obrigatória; as ferramentas administrativas solicitam autorização local. O pacote `linuxbr-server` tem dependências próprias, separadas do pacote de edição Desktop.

## Instalação e inicialização

A mídia oferece Desktop e Servidor, além dos modos de manutenção. No instalador, a página Edição define qual experiência ficará no sistema de destino. A escolha Servidor remove os componentes da sessão Desktop por uma lista explícita e por um plano APT conferido. Não usa remoção automática de dependências nem altera discos adicionais. O plano e a seleção ficam em `/var/lib/linuxbr/installation`.

A seleção persistente é registrada em `/etc/linuxbr/edition`. O gerador de inicialização aplica a sessão mínima e desabilita login automático quando a edição é Servidor. A opção temporária `linuxbr.edition=server` permite usar a experiência na mídia live. Alterações da sessão live são temporárias.

## Console

O console oferece terminal, identificação do computador, contas locais, data/hora, rede, serviços e tarefas, firewall, armazenamento, recursos opcionais, atualizações, virtualização e recuperação. Ferramentas opcionais ausentes são identificadas; a página de recursos permite instalá-las. Habilitar SSH exige escolha explícita. Liberar uma porta no firewall é uma operação separada.

O terminal mostra o caminho dentro da janela e reutiliza os comandos familiares documentados em `comandos-windows`. Ele continua sendo Bash; arquivos BAT/CMD dependem do ambiente de compatibilidade Windows. Na edição Servidor, esse ambiente é opcional.

As variáveis pessoais também podem alimentar novos serviços da conta. Depois de salvar, use Recarregar ambiente dos novos serviços; processos que já estavam em execução mantêm o ambiente anterior. A sessão gráfica recebe as variáveis ao entrar novamente. Os valores são tratados como texto literal, incluindo símbolos de dólar e aspas.

Serviços pessoais dependem da sessão, salvo habilitação explícita de Execução sem login. Essa opção exige autorização administrativa e pode manter serviços e tarefas consumindo recursos após sair. Serviços do computador podem executar desde o boot com a conta e o grupo escolhidos. O formulário permite definir tentativas de reinício, tempos máximos, atraso inicial, permissões de arquivos, limites e isolamento de rede.

## Modos restritos

Segurança, segurança com rede, segurança com terminal e manutenção aplicam máscaras transitórias a serviços, sockets, timers, paths e programas de início da sessão. Autenticação, firewall, acesso a volumes cifrados e componentes básicos de boot continuam preservados. Segurança com rede permite os componentes da conexão, mantendo serviços de compartilhamento e acesso remoto bloqueados. A edição Servidor normal mantém rede e serviços configurados; ela não é um modo de segurança.

Vídeo básico e diagnóstico são opções separadas. Vídeo básico bloqueia os módulos gráficos dos fabricantes, mantém o framebuffer genérico e usa uma sessão X11 com renderização por software. A seleção vale somente para essa inicialização; os drivers e a sessão habitual ficam preservados. O efeito depende do equipamento. Diagnóstico aumenta o registro do systemd; não promete depuração de todos os dispositivos. Os objetivos dos modos são semelhantes aos conhecidos do Windows, com mecanismos e limites próprios do Linux.

Nos modos restritos, a personalização de ambiente da conta e o perfil Bash pessoal não são carregados automaticamente pelo terminal do Linux BR. O modo com terminal mantém a autenticação do login e abre o perfil de diagnóstico por letra de unidade. Os serviços de mapeamento de rede não são iniciados pelo prompt nesse modo.

A proteção APT e sua política pertencem ao componente comum de inicialização. Remover a edição Desktop não remove o mecanismo de proteção das atualizações. A transferência de propriedade dos arquivos mantém configurações administrativas existentes.

## Recuperação

Shift + Reiniciar solicita a manutenção para um boot. As opções avançadas também estão no menu Iniciar e no carregador GRUB. A janela reúne pontos Timeshift, recuperação de arquivos por cópia e conferência SHA-256, eventos exportáveis, terminal e configuração UEFI quando disponível.

Recriar o menu GRUB guarda o menu anterior e restaura a cópia se a geração ou a validação de sintaxe falhar. Essa operação não reinstala o carregador em um disco e não repara partições. Pela mídia live, use a restauração do sistema instalado e confira o destino antes de confirmar.

Os pontos do sistema e o backup pessoal têm propósitos distintos. Uma restauração de snapshot deve usar o procedimento validado para o disco escolhido; uma cópia de documentos não substitui uma imagem completa do sistema.

## Situação das validações

Os primeiros ensaios em VM confirmaram login obrigatório, sessão mínima sem Plasma, terminal com caminho por letra, rede na sessão Servidor e alterações de contas/hostname com limpeza dos dados temporários. A compilação, a instalação pela mídia, a remoção efetiva dos pacotes Desktop e a atualização entre versões possuem validações próprias. Este guia não representa aprovação desses cenários antes de seus respectivos registros.
