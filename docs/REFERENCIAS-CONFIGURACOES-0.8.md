# Referências de organização das configurações — 0.8

Consulta: 3 de novembro de 2026. As referências abaixo orientam a organização de páginas e os nomes familiares para quem vem do Windows 10 ou 11. A implementação permanece em Qt e nos componentes reais do KDE, Chromium e XDG.

## Fontes oficiais e correspondência

| Referência Microsoft | Organização observada na documentação | Correspondência no Linux BR |
| --- | --- | --- |
| [Exploring Windows Settings](https://support.microsoft.com/en-us/windows/experience/exploring-windows-settings) | Categorias identificadas por nome e ícone, grupos de opções e páginas internas. | Índice de configurações com grupos Aplicativos, Pesquisa e Sistema; acessos com título, descrição curta e ícones distintos do tema instalado. A Central pode manter sua navegação principal. |
| [Change Default Apps in Windows](https://support.microsoft.com/en-us/windows/apps/change-default-apps-in-windows) — Windows 10 e 11 | Aplicativos → Aplicativos padrão; escolha por aplicativo, tipo ou protocolo. | Aplicativos → Aplicativos padrão: preferências nativas do KDE, editor de tipos e consulta pelo arquivo selecionado. A associação usa XDG e oferece desfazer quando existe um padrão anterior. |
| [Configure Startup applications in Windows](https://support.microsoft.com/en-gb/windows/experience/startup-boot/configure-startup-applications-in-windows) — Windows 10 e 11 | Aplicativos → Inicialização; ativar ou desativar ao entrar na conta. | Aplicativos → Inicialização: lista com origem e estado, alteração reversível do lançador da conta e acesso às preferências da sessão. Não é uma lista de serviços do sistema nem uma medição de impacto. |
| [Launch Windows Settings](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-settings) | Referência das páginas internas de Rede e Internet, Contas, Privacidade, Pesquisa e Sistema. | Mapa para a Central: Rede → conexões e compartilhamentos reais; Contas → usuários e entrada no sistema; Privacidade → permissões efetivas. Os endereços `ms-settings:` documentados para Windows não são usados no Linux BR. |
| [Change privacy settings in Windows](https://support.microsoft.com/en-us/windows/privacy/change-privacy-settings-in-windows) — Windows 10 e 11 | Permissões agrupadas em Privacidade, com páginas específicas para recursos. | Nos perfis web, câmera, microfone e notificações abrem a página nativa de permissões do Chromium, no diretório do perfil selecionado. A Central deve distinguir permissões da conta, do aplicativo e do site. |
| [Storage settings in Windows](https://support.microsoft.com/en-us/windows/experience/storage-filemanagement/storage-settings-in-windows) — Windows 10 e 11 | Sistema → Armazenamento; categorias de uso, limpeza e opções avançadas. | Sugestão para a Central: Sistema → Armazenamento, com uso medido, limpeza da conta e acesso separado a discos e backup. Cópias e conflitos ficam em Sistema e abrem a fila nativa do KDE. A página de cópias não apresenta números de armazenamento nem ações de limpeza. |
| [Understand and explore Windows Settings](https://support.microsoft.com/en-us/accessibility/windows/understand-and-explore-windows-settings) | Navegação por categorias e teclado; Contas reúne identidade e entrada. | Descrições simples, controles com nomes acessíveis e uso por Tab, Enter e barra de espaço. Voltar usa Alt+Seta para a esquerda. Contas locais e perfis web devem ter nomes distintos. |
| [Breadcrumb Bar](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/breadcrumbbar) | Caminho hierárquico visível, ancestrais acionáveis e página atual identificada. | Configurações → Aplicativos → Inicialização ou Aplicativos padrão; Configurações → Pesquisa → Arquivos e resultados; Configurações → Sistema → Cópias e conflitos. Os ancestrais abrem páginas internas reais e preservam os dados preenchidos nas páginas. |

## Imagens oficiais de referência

As imagens ficam nos sites originais; estes links permitem conferir a referência visual junto com a documentação. Nenhum arquivo de imagem, fonte, ícone ou outro recurso proprietário foi incorporado ao produto.

- [Exemplo de páginas de Configurações](https://learn.microsoft.com/en-us/windows/configuration/settings/images/settings-page-visibility.png), publicado em [Configure the Settings page visibility](https://learn.microsoft.com/en-us/windows/configuration/settings/page-visibility), documentação que abrange Windows 10 e 11.
- [Página de privacidade e câmera](https://learn.microsoft.com/en-us/windows/apps/develop/launch/images/privacyawarenesssettingsapp.png), publicada em [Launch Windows Settings](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-settings).
- [Exemplo de caminho com breadcrumbs](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/images/breadcrumb-bar.png), publicado em [Breadcrumb Bar](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/breadcrumbbar).

Também foram conferidas visualmente as figuras do [relatório oficial Microsoft — Annex 11, Section 2](https://www.microsoft.com/content/dam/microsoft/mscle/documents/presentations/Microsoft_DMA_Compliance_Report_Windows_Section_2_Annex.pdf):

| Página e figura | Leitura visual | Aplicação |
| --- | --- | --- |
| [75, figura 20](https://www.microsoft.com/content/dam/microsoft/mscle/documents/presentations/Microsoft_DMA_Compliance_Report_Windows_Section_2_Annex.pdf#page=75) | Windows 11: categorias à esquerda, caminho Aplicativos → Aplicativos padrão e busca acima da lista. | Preservar o caminho da página e separar a consulta pelo arquivo dos padrões gerais. |
| [77, figuras 22 e 23](https://www.microsoft.com/content/dam/microsoft/mscle/documents/presentations/Microsoft_DMA_Compliance_Report_Windows_Section_2_Annex.pdf#page=77) | Windows 11: linhas com ícone, nome e acesso à página seguinte; página interna com caminho de três níveis e grupos de tipos. | Acessos internos com ícones semânticos, título e descrição; ancestrais do caminho acionáveis. |
| [79, figura 26](https://www.microsoft.com/content/dam/microsoft/mscle/documents/presentations/Microsoft_DMA_Compliance_Report_Windows_Section_2_Annex.pdf#page=79) | Windows 10: Aplicativos padrão e Inicialização na mesma seção; nome da página em destaque e opções por finalidade. | Reunir Inicialização e Aplicativos padrão em Aplicativos, mantendo as funções reais do KDE e as preferências da conta. |

## Aplicação e limites

`desktopflows08.py` organiza somente funções já existentes: pesquisa, inicialização, aplicativos padrão e cópias. As páginas mantêm os mesmos entrypoints e usam os mesmos serviços nativos. Não são acrescentadas categorias vazias de Rede, Contas ou Privacidade nessa seção; esses destinos precisam corresponder às páginas reais da Central.

Os blocos separam a ação principal, as configurações relacionadas e a explicação do comportamento. O texto acompanha a fonte configurada na sessão e a área interna permite rolagem com texto ampliado. As ações de abrir componentes têm nomes acessíveis específicos, mesmo quando o botão visível diz apenas Abrir. Navegar pelas categorias não abre programas nem modifica preferências.

Validação: seis testes de navegação e teclado, mais treze regressões dos fluxos de perfis e desktop. As páginas reais de Inicialização e Aplicativos padrão foram capturadas a 930 × 720, com fontes de 11 e 18 pontos em diretórios privados de teste; o conteúdo usa rolagem vertical, sem rolagem horizontal. A inspeção inclui também o índice por categorias. As capturas usam somente lançadores de laboratório.

Para as demais páginas, recomenda-se manter o mesmo caminho, os mesmos grupos e descrições curtas: armazenamento e limpeza separados de backup; contas locais separadas de sessões web; conexão de rede separada de publicação de uma pasta; estado de proteção separado da ação que faz a verificação. Capacidades indisponíveis devem explicar o motivo, sem simular resultados ou apresentar controles sem implementação.
