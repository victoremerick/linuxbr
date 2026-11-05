# Linux BR 0.9 — implementação e critérios de aceitação

Estado: candidata Beta 1 em validação. Este documento mantém o escopo aprovado; a presença de um requisito não comprova implementação ou validação. As evidências da versão devem distinguir componentes, pacotes, mídia live, instalação e atualização. O relatório entregue com os artefatos identifica a fonte congelada, os checksums e os cenários efetivamente executados.

## Evolução do sistema

- Pesquisa integrada no menu Iniciar e atalhos diretos às páginas das Configurações, incluindo variáveis de ambiente, agendador, aplicativos, rede, impressoras e recuperação. Reconhecer termos familiares do Windows.
- Melhorar apresentação da Loja, metadados, fontes, permissões, fila e recuperação de instalações.
- Central de dispositivos e diagnóstico; integração de firmware para equipamentos suportados.
- Backup pessoal, histórico de arquivos e recuperação gráfica do sistema.
- Canais de atualização, verificações prévias e manutenção automática dos metadados do repositório APT.
- Evoluir compatibilidade Windows, compartilhamento em rede, virtualização e migração de arquivos.
- Uniformizar português, ícones, acessibilidade, escalas e navegação por teclado; corrigir atualização do título/caminho nas Propriedades após renomear com Aplicar.
- Validar instalação, atualização, recuperação e preservação de dados; homologação física depende de equipamentos disponíveis.

## Recursos opcionais e controle de inicialização

Requisitos confirmados para a 0.9:

- Janela “Ativar ou desativar recursos do Linux BR”, com acesso pelas Configurações e menu Iniciar.
- Controlar compatibilidade Windows, virtualização, compartilhamento, acesso remoto, impressão/digitalização, Bluetooth, indexação e ferramentas de desenvolvimento.
- Distinguir desativar serviços de remover pacotes; mostrar espaço ocupado, dependências, impacto e necessidade de reiniciar. Não prometer economia de memória por apenas remover programas inativos.
- Perfis Essencial, Pessoal, Jogos e Desenvolvimento, com prévia e reversão das mudanças; proteger componentes essenciais e tarefas em andamento.
- Central de Configuração do Sistema, inspirada no msconfig, com abas Geral, Inicialização do sistema, Serviços, Programas de inicialização e Ferramentas.
- Reunir entradas de início da sessão, serviços de usuário/sistema e tarefas disparadas no login/inicialização, identificando origem e escopo sem duplicar controles conflitantes.
- Exibir nome, descrição, fornecedor quando conhecido, estado, comando, localização e impacto medido quando disponível; nunca inventar métricas de impacto.
- Habilitar/desabilitar de forma reversível, filtrar serviços essenciais, abrir local do arquivo e mostrar dependências. Exigir autenticação para alterações globais.
- Inicialização normal, diagnóstica e seletiva; configurar padrão e tempo de menu com validação e caminho de retorno. Não oferecer quantidade de CPUs/memória como suposta otimização.

## Criador e gerenciador gráfico de serviços

Requisito confirmado: oferecer interface própria para criar, consultar, editar e administrar serviços, acessível pelo menu Iniciar, pesquisa e Configurações. Integrar com a Central de Configuração do Sistema sem duplicar estados.

- Lista pesquisável de serviços de usuário e do sistema, com nome amigável, descrição, origem, estado atual, inicialização configurada e indicação de componentes essenciais.
- Assistente de criação: nome/identificador, descrição, executável por seletor de arquivo, argumentos, diretório de trabalho, usuário/grupo de execução e variáveis de ambiente.
- Escolher serviço de usuário ou sistema e explicar quando cada um executa. Distinguir login, boot e permanência após logout; execução de serviço de usuário sem sessão exige configuração explícita.
- Configurar início automático/manual/desativado, atraso quando aplicável e dependências. Distinguir desabilitar início automático de bloquear toda ativação, incluindo sockets, timers e dependências.
- Configurar comportamento de processo, parada, reinício após falha, intervalo, limite de tentativas e tempos máximos; evitar reinícios infinitos por padrão.
- Opções avançadas para limites de CPU/memória, permissões de arquivos, acesso à rede e isolamento, explicando impactos e incompatibilidades.
- Prévia legível e prévia da unidade systemd gerada; validar sintaxe, caminhos, usuário e dependências antes de gravar. Gerar comandos com argumentos tratados corretamente, sem shell implícito ou concatenação insegura.
- Instalar o serviço e iniciá-lo são ações distintas; a criação não deve executar automaticamente o programa sem escolha explícita.
- Ações de iniciar, parar, reiniciar, recarregar quando suportado, habilitar, desabilitar e bloquear, com explicação de efeitos e autenticação administrativa para mudanças no sistema.
- Tela de detalhes: estado, PID, último resultado/código de saída, horários, reinícios, consumo medido de CPU/memória, dependências e serviços dependentes; valores indisponíveis devem ser identificados.
- Logs integrados com atualização ao vivo, filtros, busca e exportação; proteger segredos, respeitar permissões e limitar uso de memória no visualizador.
- Serviços fornecidos por pacotes devem ser personalizados por overrides, preservando as unidades originais; oferecer comparação e restauração da configuração.
- Editar, duplicar, exportar/importar definição e excluir serviços próprios com revisão explícita. Importações não podem executar conteúdo automaticamente; não remover arquivos de unidades pertencentes a pacotes.
- Backup da configuração antes de alterações, aplicação atômica e restauração em caso de erro; verificar o estado real após cada ação, sem mostrar sucesso apenas porque o comando foi enviado.
- Identificar programas gráficos e orientar para inicialização da sessão quando não forem adequados como serviço. Tarefas pontuais devem ter encaminhamento para o agendador existente.
- Validar criação de serviço de usuário/sistema, caminhos com espaços, falhas, limites de reinício, logs, permissões, overrides, dependências, ativação por socket/timer, reinicialização e remoção sem resíduos.

## Recuperação e modos de inicialização

- Shift + Reiniciar no menu de energia e tela de login deve solicitar o ambiente de recuperação para a próxima inicialização; fornecer também botão explícito em Recuperação e entrada acessível no boot.
- Oferecer F8 durante a janela do carregador para as opções avançadas, com alternativa visível para equipamentos cujo firmware capture a tecla. Validar UEFI e BIOS.
- Ambiente de recuperação independente da sessão instalada, acessível também pela mídia live: continuar, selecionar dispositivo de boot quando suportado, solucionar problemas, opções avançadas e desligar.
- Opções avançadas: diagnóstico/reparo de boot, restauração de snapshot, restauração de backup, recuperação de atualização com procedimento validado, terminal, configurações de inicialização e firmware UEFI quando disponível.
- Terminal de manutenção com orientação em português, localização visível, comandos familiares documentados e acesso às ferramentas Linux necessárias; não apresentar equivalência completa com CMD/PowerShell.
- Matriz obrigatória de modos, serviços permitidos, serviços bloqueados e testes reais:
  - Normal: configuração habitual.
  - Segurança: drivers e serviços mínimos para login e diagnóstico, rede desativada, sem programas de início automático, serviços opcionais ou VMs automáticas.
  - Segurança com rede: mesma base restrita, habilitando somente componentes necessários à conexão; compartilhamento, descoberta e acesso remoto permanecem desativados por padrão.
  - Segurança com terminal: sessão de terminal sem desktop, rede desativada por padrão e autenticação obrigatória.
  - Vídeo básico: configuração gráfica conservadora para recuperar problemas de vídeo, identificada separadamente do modo de segurança.
  - Diagnóstico de boot: registrar inicialização e permitir consultar/exportar logs; opções específicas de depuração somente se implementadas e testadas.
- Traduzir objetivos dos modos Windows em restrições verificáveis no Linux; documentar diferenças de drivers, autenticação e serviços. Não prometer bloqueios tecnicamente idênticos entre sistemas.
- Não desativar autenticação, criptografia, firewall ou validação de boot como efeito implícito do modo de manutenção. Desbloquear volumes cifrados com credenciais válidas; alterações administrativas exigem autorização local.
- Seleção temporária vale por um boot, salvo escolha persistente explícita; garantir saída do modo restrito e tratamento de falhas sem ciclo de reinicialização.
- Testar restrições efetivas, incluindo serviços ativados por sockets, tarefas agendadas, autostart e VMs; não limitar a implementação a nomes de menus.

## Edição sem desktop completo — experiência de servidor

- Oferecer seleção no boot live e no instalador entre Desktop e Servidor sem desktop completo.
- Servidor com fundo preto e janela de terminal/console de configuração, inspirado na experiência Hyper-V Server/Server Core; sessão mínima própria, sem iniciar Plasma completo.
- Menu em português operável por teclado para nome do computador, usuários, rede, DNS, data/hora, atualizações, acesso remoto, firewall, armazenamento, virtualização, diagnóstico, reiniciar/desligar e terminal livre.
- Priorizar gerenciamento de host de virtualização e serviços; indicar capacidades indisponíveis e permitir instalar recursos opcionais com confirmação.
- Instalação Servidor deve selecionar pacotes próprios, evitando dependência do desktop completo; modo live deve explicar alterações temporárias e discos disponíveis antes de operações.
- Login autenticado, sem shell administrativo automático; habilitação de administração remota explícita. Validar consumo em repouso e preservação da configuração após reiniciar.

## Detalhes de conexão em interface gráfica

- Substituir a exibição principal de saída bruta de ifconfig por campos, ícones e seções legíveis.
- Mostrar adaptador, estado, tipo de conexão, IPv4/IPv6, prefixo/máscara, gateway, DNS, DHCP, MAC, velocidade negociada quando disponível, rota padrão e estado de conectividade.
- Para Wi-Fi: SSID, intensidade, frequência e segurança; para VPN e interfaces virtuais: tipo, vínculo e estado quando disponíveis. Usar “Não disponível” para dados ausentes.
- Ações: copiar campo/todos os detalhes, editar conexão, abrir diagnóstico e renovar concessão quando suportado, avisando sobre interrupção da conexão.
- Usar dados estruturados do gerenciador de rede; saída técnica opcional em seção avançada/exportação, nunca como interface principal.
- Validar Ethernet, Wi-Fi, VPN, adaptadores virtuais, múltiplos endereços, conexão sem internet e estado desconectado.

Referências funcionais:

- https://support.microsoft.com/en-us/windows/experience/startup-boot/windows-startup-settings
- https://learn.microsoft.com/windows-hardware/manufacture/desktop/windows-recovery-environment--windows-re--technical-reference
- https://learn.microsoft.com/en-gb/windows-server/administration/server-core/server-core-sconfig

## Servidor de catálogo e atualizações de webapps

Requisito confirmado: implementar na 0.9 um servidor PHP com banco MySQL e interface Angular, preparado para hospedagem compartilhada Hostinger Web Hosting.

### Hospedagem e entrega

- API PHP via HTTPS e persistência MySQL com migrações de esquema.
- Angular compilado previamente e entregue como arquivos estáticos; não depender de servidor Node, SSR, acesso root, contêineres ou processos permanentes na hospedagem.
- Verificações periódicas em lotes limitados por cron PHP, com trava contra execução simultânea, retomada e limites de tempo/requisições.
- Documentar instalação pelo painel de hospedagem, banco, HTTPS, rotas, cron, backup e atualização; confirmar versões e extensões no plano usado antes da implantação.
- Credenciais e chaves privadas fora da área pública; API administrativa autenticada, permissões e registro de alterações.

### Padrão público versionado

- Especificar e documentar um protocolo JSON próprio, com versão de esquema, identificador estável da fonte e do aplicativo, revisão do catálogo e de cada registro, data de publicação e validade.
- Registros: nome, descrição, categorias, domínio verificado, URL inicial, favicon, capturas, disponibilidade de aplicativo Linux, requisitos e notas de alterações.
- Publicar descoberta da fonte em endereço documentado, catálogo pesquisável/paginado e manifesto de revisões; prever fontes adicionais configuráveis na Loja.
- Catálogos assinados, verificação no cliente, confiança explícita ao adicionar fontes, rotação de chaves e rejeição de conteúdo expirado/inválido; manter última cópia válida para consulta offline.
- Validar URLs, redirecionamentos, tamanho e tipo dos recursos; impedir acesso do verificador a redes privadas e serviços internos.
- Metadados não podem fornecer comandos arbitrários para execução no cliente.

### Descoberta, publicação e notificações

- Painel Angular para cadastrar, revisar, categorizar, publicar, desativar e consultar histórico dos aplicativos; submissões passam por revisão.
- Verificar disponibilidade de sites, mudanças de domínio, favicon e manifesto web quando existente; alterações detectadas entram para revisão antes da publicação.
- Usar sinais oficiais de versão ou changelog quando disponíveis. Mudança de HTML, data HTTP ou manifesto não prova lançamento de nova versão.
- Distinguir atualização do cadastro/integração local, atualização do próprio serviço online e atualização de Chromium distribuída pelo APT.
- Serviços online normalmente mudam no servidor do fornecedor: não inventar versões nem apresentar reinstalação como necessária. Quando não houver informação verificável, indicar versão desconhecida.
- Cliente compara revisões, exibe alterações na Loja e sinaliza atualizações aplicáveis aos webapps instalados, sem repetir avisos já tratados.
- Aplicar alterações preservando perfis, cookies, sessões e preferências. Mudanças de domínio, URL inicial ou permissões exigem confirmação e não transferem sessões automaticamente.
- Não enviar histórico de navegação, cookies, credenciais ou conteúdo dos perfis ao catálogo.

### Critérios de aceitação

- Publicar e consumir uma fonte de teste, localizar um webapp, instalá-lo, publicar nova revisão e receber/aplicar o aviso preservando perfis.
- Conferir catálogo offline, falha de rede, assinatura inválida, expiração, duplicatas entre fontes, alteração de domínio e ausência de versão oficial.
- Validar implantação com PHP/MySQL e Angular estático sob limites equivalentes aos do plano contratado; registrar separadamente validação local e publicação real na Hostinger.

Referências de hospedagem:

- https://www.hostinger.com/support/which-programming-languages-and-frameworks-are-supported-at-hostinger/
- https://www.hostinger.com/support/1583465-how-to-set-up-a-cron-job-at-hostinger/
- https://www.hostinger.com/support/6976044-parameters-and-limits-of-hosting-plans-in-hostinger/
