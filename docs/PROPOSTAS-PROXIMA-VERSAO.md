# 100 propostas para a próxima versão do Linux BR

O escopo complementa a [instalação e configuração inicial](INSTALACAO-E-CONFIGURACAO-INICIAL.md), o [planejamento da 1.1](VERSAO-1.1.md) e as [entregas da 1.1.1](VERSAO-1.1.1.md). A primeira rodada deve priorizar os itens 1, 3, 8, 11–14, 27, 51–55 e 61–62. Cada entrega deve ter um caminho de acesso na interface, um guia com captura da versão instalada e um critério de aceite registrado.

## Instalação e migração

1. **Simulação da instalação.** Mostrar a tabela de partições, as operações previstas e o espaço resultante antes de gravar no disco.
2. **Mapa visual de armazenamento.** Identificar discos por fabricante, modelo, capacidade e conexão, com volumes alinhados proporcionalmente ao espaço ocupado.
3. **Detecção de volumes protegidos.** Sinalizar BitLocker, LUKS e hibernação do Windows antes de oferecer redimensionamento ou importação.
4. **Pré-verificação do notebook.** Testar teclado, touchpad, áudio e vídeo na mídia live e levar o resultado para a configuração inicial.
5. **Guia de configuração do firmware.** Explicar o estado de UEFI, Secure Boot e virtualização e indicar o próximo passo para cada requisito detectado.
6. **Revisão da migração por pasta.** Exibir tamanho, destino e conflitos de Documentos, Área de Trabalho e Downloads antes de copiar.
7. **Migração de favoritos.** Importar favoritos de perfis acessíveis do Edge, Chrome e Firefox para um perfil escolhido pelo usuário.
8. **Retomada da configuração inicial.** Reabrir no último passo confirmado após queda de energia ou reinício e impedir a criação duplicada de contas.
9. **Preparação com teclado assistivo.** Disponibilizar teclado na tela e leitor de tela já no seletor de layout e na criação da conta.
10. **Mídia de implantação com predefinições.** Exportar um arquivo de configuração sem segredos para reaplicar idioma, edição e preferências em outra instalação.

## Loja e distribuição

11. **Página única por produto.** Reunir DEB, Flatpak, Snap, Homebrew, Windows e Web em uma ficha quando as identidades forem confirmadas.
12. **Prévia de impacto da instalação.** Mostrar espaço, dependências, permissões e serviços que a operação pode adicionar.
13. **Origem e mantenedor por formato.** Exibir fonte, assinatura quando disponível e se o empacotamento é mantido pelo fornecedor ou pela comunidade.
14. **Catálogo disponível sem conexão.** Preservar a última revisão válida em disco, registrar sua data e indicar quais ações exigem internet.
15. **Busca por equivalentes do Windows.** Mostrar alternativas para tarefas específicas e informar diferenças em formatos de arquivo e recursos.
16. **Comparação entre aplicativos.** Colocar lado a lado licença, idioma, requisitos, modo offline e formatos suportados.
17. **Aviso de aplicativo descontinuado.** Mostrar a situação da fonte, a data da retirada e o caminho para preservar os dados ao migrar.
18. **Pausa na atualização de um aplicativo.** Permitir congelar uma versão por prazo definido e exibir o motivo junto à atualização pendente.
19. **Prévia de desinstalação com dados.** Identificar arquivos de configuração, cache e prefixos associados e permitir conservar cada conjunto.
20. **Coleções de aplicativos por tarefa.** Oferecer seleções de estudo, criação, trabalho e jogos com revisão individual antes de instalar.

## Explorador e arquivos

21. **Painel duplo com cópia entre lados.** Exibir origem e destino na mesma janela e oferecer copiar ou mover a seleção com verificação de conflitos.
22. **Recuperação de abas fechadas.** Reabrir o último conjunto de pastas com posição das abas e histórico de navegação da sessão.
23. **Etiquetas por projeto.** Marcar arquivos com rótulos persistentes e abrir a lista correspondente a partir do painel lateral.
24. **Consultas salvas.** Guardar filtros de nome, tipo, data e tamanho e reexecutá-los em uma ou mais pastas.
25. **Comparação de pastas.** Listar arquivos novos, ausentes e diferentes, com opção de verificar conteúdo por soma de verificação.
26. **Colagem especial por formato.** Colar um caminho, criar um link ou copiar o conteúdo como texto quando a origem oferecer essas opções.
27. **Cópia verificável.** Conferir a integridade no destino e retomar após desconexão sem declarar concluído um arquivo incompleto.
28. **Detecção de nomes incompatíveis.** Avisar sobre nomes inválidos e colisões de maiúsculas e minúsculas antes de copiar para NTFS, FAT ou compartilhamentos.
29. **Prévia com proteção de privacidade.** Exibir miniaturas locais e permitir bloquear prévias em pastas privadas ou compartilhadas.
30. **Desfazer operações em lote.** Reverter movimentações e renomeações recentes, com revisão quando um destino já tiver sido ocupado.

## Área de trabalho e produtividade

31. **Grupos de janelas restauráveis.** Salvar um conjunto de aplicativos e suas posições e reconstruí-lo em outra sessão.
32. **Layouts personalizados de encaixe.** Definir divisões de tela por monitor e usar teclado ou arraste para encaixar janelas.
33. **Perfis de monitores por local.** Salvar escala, orientação, posição e tela principal para cada combinação de monitores e docks.
34. **Mover janela para a tela ativa.** Recuperar com um atalho uma janela que ficou fora da área visível após desconectar um monitor.
35. **Horários de concentração.** Silenciar notificações em períodos definidos e permitir exceções por aplicativo e prioridade.
36. **Notificações por área de trabalho.** Associar aplicativos a espaços de trabalho e abrir o aviso no espaço correspondente.
37. **Espaços de trabalho nomeados por tarefa.** Guardar um conjunto de nomes, atalhos, papel de parede e aplicativos sugeridos.
38. **Captura com anotações e mascaramento.** Cortar uma imagem e cobrir informações sensíveis antes de copiá-la ou enviá-la.
39. **Comandos rápidos no Iniciar.** Criar ações locais para abrir uma combinação de pastas, links e aplicativos com pesquisa pelo nome.
40. **Controles por aplicativo no painel.** Gerenciar mídia e microfone da janela selecionada a partir da barra de tarefas.

## Acessibilidade e periféricos

41. **Preferências de acessibilidade por aplicativo.** Definir escala, contraste e redução de animações para programas específicos.
42. **Indicador de foco do teclado.** Realçar o controle ativo e oferecer um modo de demonstração de atalhos para primeiros passos.
43. **Leitura em voz alta de texto selecionado.** Usar voz local em português com controle de velocidade e pausa.
44. **Teste orientado do leitor de tela.** Percorrer Iniciar, barra de tarefas, campos e diálogos e identificar controles sem descrição.
45. **Remapeamento de teclas pela interface.** Configurar teclas especiais e camadas por teclado, com botão para desfazer.
46. **Calibração de mesa digitalizadora.** Mapear área ativa, pressão, botões e monitor de destino.
47. **Perfis de toque por dispositivo.** Configurar cliques, arraste e gestos no touchpad com demonstração interativa.
48. **Teste e calibração de controles de jogo.** Visualizar eixos, zonas mortas, botões e vibração, com perfil por dispositivo.
49. **Destino de áudio por tipo de uso.** Selecionar separadamente saídas para chamadas, mídia e jogos e escolher o dispositivo de reserva.
50. **Perfis de energia por dock e carregador.** Aplicar limites de desempenho, tela e suspensão compatíveis com o hardware conectado.

## Recuperação e confiabilidade

51. **Teste de recuperação sem alterar a instalação.** Validar se existe um ponto de restauração legível e estimar o espaço necessário para usá-lo.
52. **Comparação entre pontos de recuperação.** Mostrar pacotes, serviços e configurações que mudaram antes de confirmar a restauração.
53. **Verificação após primeiro boot atualizado.** Conferir sessão, rede e armazenamento e registrar falhas para o responsável pela próxima onda.
54. **Histórico da saúde do armazenamento.** Registrar evolução de erros SMART e NVMe e apontar mudanças que exigem atenção.
55. **Mídia de recuperação personalizada.** Preparar uma unidade externa com ferramentas offline, identificação da edição e instruções de restauração.
56. **Reinstalação com preservação de dados.** Identificar contas e partições de dados e apresentar as operações que podem ser executadas com segurança.
57. **Reparo de perfil de usuário.** Testar uma sessão limpa e restaurar seletivamente preferências quebradas de painel e janelas.
58. **Linha do tempo de alterações do sistema.** Correlacionar atualizações, reinícios, troca de periféricos e falhas observadas.
59. **Diagnóstico de reinícios inesperados.** Distinguir perda de energia, pane do kernel e desligamento explícito a partir dos eventos disponíveis.
60. **Validação programada de backups.** Conferir índices e integridade de uma amostra e registrar quando um arquivo foi recuperado com sucesso.

## Segurança e privacidade

61. **Painel de permissões da sessão.** Rever acessos concedidos a câmera, microfone, localização, notificações e compartilhamento de tela.
62. **Diagnóstico dos portais de compartilhamento.** Distinguir falha ao escolher uma tela, ausência de PipeWire e restrições do aplicativo.
63. **Bloqueio ao remover chave física.** Permitir associar uma chave compatível à sessão e configurar como o retorno deve ser autenticado.
64. **Revisão de aplicativos que executam em segundo plano.** Mostrar consumo e permitir revogar inicialização ou permissões específicas.
65. **Acesso temporário a pastas compartilhadas.** Criar concessões com prazo, escopo de leitura ou edição e revogação centralizada.
66. **Histórico de consentimentos administrativos.** Registrar solicitação, aplicativo, horário, conta e resultado das autorizações.
67. **Ambiente isolado para abrir arquivos.** Oferecer abertura descartável de documentos com acesso restrito aos diretórios pessoais.
68. **Central de senhas de recuperação.** Mostrar como verificar, registrar e exportar com proteção as chaves de volumes compatíveis.
69. **Auditoria de certificados locais.** Mostrar emissor, validade, origem e quais certificados foram adicionados pela organização.
70. **Controle de área de transferência sensível.** Excluir itens por tipo ou origem e aplicar expiração aos itens permitidos no histórico.

## Aplicativos Windows, jogos e webapps

71. **Relatório por versão de Wine e Proton.** Vincular evidências à versão do aplicativo, executor, GPU e recursos exercitados.
72. **Cópia de segurança do prefixo antes de atualizar.** Preservar a configuração anterior do aplicativo e permitir restauração independente.
73. **Central de componentes Windows.** Explicar quais programas usam cada runtime e instalar dependências autorizadas no prefixo correspondente.
74. **Diagnóstico de autenticação em aplicativos Windows.** Mostrar se o retorno do navegador chegou ao aplicativo sem expor códigos ou tokens.
75. **Verificação de integração das janelas Windows.** Conferir minimizar, maximizar, restauração, atalhos e múltiplos monitores por executor.
76. **Modo de recuperação gráfica de um jogo.** Ajustar resolução e janela externamente quando o jogo abrir fora da tela ou falhar após mudar de monitor.
77. **Alternância de renderizador por jogo.** Escolher backend gráfico e reiniciar apenas o jogo, com registro da configuração anterior.
78. **Gerenciador de permissões por perfil web.** Permitir que perfis do mesmo aplicativo tenham regras diferentes para câmera e notificações.
79. **Revisão de alteração do endereço de um webapp.** Solicitar confirmação de mudança de domínio e oferecer uma sessão limpa após a troca.
80. **Restauração de atalhos web sem credenciais.** Exportar nomes, ícones e preferências dos perfis e recriar os atalhos em outro computador.

## Máquinas virtuais

81. **Medição de consumo por VM.** Mostrar histórico de CPU, RAM, disco e rede com intervalos selecionáveis.
82. **Orçamento de recursos por grupo.** Definir limites para máquinas de laboratório, trabalho e produção e indicar quando a soma excede o host.
83. **Mapa da topologia virtual.** Mostrar VMs, interfaces, redes, pontes, VLANs e caminho até a interface física.
84. **Importação guiada de VHD e VHDX.** Converter uma cópia do disco e sugerir firmware e controladora a partir das informações disponíveis.
85. **Reversão assistida de checkpoint órfão.** Inspecionar a cadeia de discos antes de propor consolidação ou recuperação.
86. **Restauração de arquivos de uma VM.** Montar uma imagem compatível para leitura e recuperar arquivos sem iniciar o sistema convidado.
87. **Catálogo de modelos administrados.** Publicar perfis de CPU, memória, firmware e rede com revisão e identificação da versão.
88. **Credenciais descartáveis para laboratórios.** Gerar um acesso temporário à VM e expirar a autorização na data definida.
89. **Checagem de compatibilidade de migração.** Verificar CPU, firmware, recursos e conectividade do destino antes do horário da mudança.
90. **Delegação de mídia virtual.** Dar a um operador permissão temporária para anexar uma ISO aprovada a uma VM específica.

## Administração de computadores

91. **Simulação de política por dispositivo.** Exibir quais regras atingiriam um computador e explicar precedência e exceções antes de publicar.
92. **Revisão de divergência de configuração.** Comparar estado esperado e observado, identificar ajustes locais e oferecer correção aprovada.
93. **Aprovação em duas etapas para políticas críticas.** Exigir dois papéis distintos para publicar regras que alteram login ou acesso remoto.
94. **Pausa de políticas por prazo.** Autorizar uma exceção temporária por dispositivo e reativar a regra ao encerrar a janela aprovada.
95. **Inventário de aplicativos por formato.** Distinguir a origem, versão e executor de cada instalação em relatórios organizacionais.
96. **Manutenção conforme horário local.** Calcular janelas por fuso, observar sessões em uso e registrar quando uma tarefa foi adiada.
97. **Testes de saúde personalizados por onda.** Permitir que a organização defina serviços e aplicativos obrigatórios antes de promover um lote.
98. **Acesso de suporte com consentimento temporário.** Exibir quem solicitou, o escopo concedido e um controle para encerrar a sessão.
99. **Exportação de auditoria por intervalo.** Gerar um registro verificável de políticas, exceções e ações administrativas para revisão.
100. **Retirada de computador da organização.** Revogar as credenciais gerenciadas, remover regras organizacionais e confirmar o estado ao final.
