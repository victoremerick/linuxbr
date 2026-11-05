# Linux BR 0.8 — implementação e critérios de conclusão

Estado: implementação da 0.8 Beta 1, iniciada em 3 de novembro de 2026. Este documento mantém os requisitos da edição e seus critérios de conclusão. O código e os testes de componentes não substituem a validação da imagem distribuída, registrada separadamente em [validação da Beta 1](VALIDACAO-0.8-BETA1.md).

## Objetivo

Facilitar a migração do Windows e as tarefas diárias, com integração entre arquivos, aplicativos, contas web, rede, atualização e recuperação. Reutilizar os serviços do Debian e do KDE, mantendo as preferências e os dados existentes.

O desktop familiar, os atalhos Windows, o terminal com letras de unidade, os comandos e BAT/CMD, os favicons, os perfis web, o Gerenciador de Tarefas independente e a tela Ctrl+Alt+Del já fazem parte da base. A 0.8 deve preservar esses recursos e completar seus fluxos.

## Propriedades de arquivos e pastas

Prioridade central da versão. Abrir por **botão direito → Propriedades** ou **Alt+Enter**, no Explorador de arquivos e na área de trabalho, com uma única entrada principal. Aproveitar o diálogo nativo do KIO e suas extensões; uma janela auxiliar separada não satisfaz, sozinha, a integração solicitada.

A janela terá **OK**, **Cancelar** e **Aplicar**, ícones distintos por função e abas apropriadas ao item selecionado. Consultar propriedades não executa o arquivo nem altera permissões. Opções indisponíveis devem explicar o motivo. Operações que já começaram, como cópia, restauração ou compartilhamento, precisam apresentar sua própria confirmação e resultado, sem sugerir que Cancelar desfaz ações concluídas.

| Aba | Requisitos |
| --- | --- |
| Geral | Nome, ícone, tipo, aplicativo padrão, localização com letra de unidade quando houver, caminho real copiável, tamanho e espaço ocupado quando disponíveis; datas de criação, modificação e acesso fornecidas pelo sistema. Pastas: quantidade de arquivos/subpastas e cálculo de tamanho com progresso e cancelamento. |
| Detalhes | Metadados disponíveis por formato: dimensões de imagem, duração e codecs de mídia, autor e título de documento, versão e fabricante declarados no executável. Distinguir dados declarados de informações verificadas. |
| Segurança | Proprietário, grupo e acesso para usuários/grupos, com leitura, alteração e execução ou acesso à pasta. Editor avançado de ACL quando suportado, indicação de permissões efetivas e opção explícita de aplicar às subpastas com prévia do alcance. |
| Validação | Calcular SHA-256 e SHA-512 sob demanda, copiar e comparar com uma referência fornecida. Exibir progresso, cancelamento e resultado. Assinaturas só recebem estado de verificação quando houver verificador e cadeia de confiança suportados; nos demais casos, informar que não foram verificadas. |
| Compatibilidade | Para EXE/MSI: arquitetura, ambiente Wine associado, diagnóstico existente, configuração do Wine e opções compatíveis de versão Windows, vídeo e escala. Permitir abrir ou instalar mediante ação explícita. Informar quando uma alteração afeta outros programas do mesmo ambiente. |
| Compartilhamento | Para pastas locais elegíveis: publicar ou interromper compartilhamento SMB, escolher nome e usuários/grupos, configurar leitura ou alteração, mostrar endereço `\\computador\pasta` e `smb://computador/pasta`, copiar endereço e verificar acesso. Acesso convidado somente por escolha explícita. |
| Versões anteriores | Relacionar o arquivo ou pasta a cópias pessoais existentes, mostrar datas disponíveis, abrir uma versão e restaurar preferencialmente para outro destino. Informar quando não há histórico ou destino conectado. Usar o backup pessoal; os pontos de sistema continuam no fluxo Timeshift. |
| Atalho | Para lançadores e links: destino, argumentos, pasta de trabalho e ícone, com indicação clara do formato e validação antes de salvar. Atalhos Windows `.lnk` não são tratados automaticamente como lançadores Linux. |

### Comportamento por origem

- **Arquivos locais:** mostrar as capacidades efetivas do sistema de arquivos. Permissões POSIX e ACL de acesso/padrão devem respeitar a máscara efetiva e a propriedade existente.
- **NTFS e unidades removíveis:** considerar driver, montagem somente para leitura e capacidades reais. Não apresentar um editor de permissões Windows como funcional quando a montagem não o oferece.
- **SMB:** consultar o servidor pelos mecanismos nativos. Alterações de permissões remotas dependem de suporte e autorização; a aba pode ser somente de leitura. Publicar uma pasta local e acessar um compartilhamento remoto são operações diferentes.
- **Links simbólicos:** mostrar o destino e distinguir propriedades do link e do alvo. Aplicação recursiva não deve atravessar links ou outros volumes por consequência de uma seleção genérica.
- **Vários itens:** apresentar totais, valores mistos e o alcance de cada alteração; não substituir valores diferentes por um padrão silencioso.

Data de criação ausente aparece como indisponível; `ctime` não deve ser rotulado como criação. Metadados de acesso e espaço ocupado podem ser limitados pelo sistema de arquivos ou servidor. Cálculos de pastas inacessíveis devem identificar resultados parciais.

Hashes correspondentes confirmam igualdade com a referência, sem comprovar ausência de malware ou identidade do fornecedor. Uma eventual ação de antivírus depende de ferramenta e assinaturas disponíveis e informa o resultado e sua data, sem envio automático de arquivos a serviços externos.

A aba Compatibilidade não transforma um ambiente Wine em isolamento de segurança. Uma opção familiar de execução administrativa não pode ser traduzida em execução do Wine com `sudo` ou como root. Autorizações para alterações de sistema devem usar o mecanismo nativo, com alcance explícito.

O compartilhamento deve reutilizar Samba e integrar a extensão nativa de propriedades quando compatível com a base. Configurar somente a pasta selecionada, apresentar permissões locais e de rede e conferir o estado real do serviço e do firewall. Preservar configurações e compartilhamentos anteriores. Interromper o compartilhamento mantém os arquivos.

### Critérios de conclusão das propriedades

1. Abrir a janela real por clique direito e Alt+Enter para arquivo, pasta, executável, atalho e seleção múltipla, sem entradas duplicadas.
2. Conferir tamanhos e metadados com arquivos conhecidos, acentos, espaços e pasta grande; cancelar cálculo sem travar o Explorador.
3. Aplicar permissões em uma árvore de teste, conferir acesso efetivo e limites de recursão, cancelar edição sem mudanças e recusar alteração sem autorização.
4. Comparar hashes corretos e divergentes; cancelar a leitura; não executar o item durante inspeção.
5. Selecionar e configurar um ambiente Wine, executar o diagnóstico existente e conferir preservação das configurações dos demais ambientes.
6. Criar um compartilhamento autenticado em laboratório, ler/escrever conforme a permissão, recusar usuário não autorizado e interromper a publicação preservando os dados.
7. Relacionar uma cópia pessoal existente ao arquivo, abrir e restaurar uma versão com integridade conferida; apresentar ausência de backup de forma correta.
8. Exercitar item somente para leitura, SMB indisponível, ausência de ACL, link simbólico e metadados ausentes sem inventar resultados.

## Demais frentes da versão

| Frente | Entrega proposta |
| --- | --- |
| Trazer arquivos do Windows | Selecionar pastas em disco ou backup, prever espaço, tratar duplicatas, permitir cancelamento e produzir relatório de integridade, preservando a origem. |
| Loja integrada | Instalar, atualizar e remover pela mesma interface, com progresso, histórico e origem. Reutilizar os gerenciadores nativos e as confirmações dos instaladores Windows, sem operações concorrentes sobre o mesmo gerenciador. Distinguir remoção de atalho, programa, ambiente e dados. |
| Programas Windows e jogos | Receitas de configuração por aplicativo e versão, dependências identificadas e reparação do ambiente. Matriz de testado, parcial e não testado, incluindo alternativa Linux ou web quando houver. Melhor integração com Steam/Proton, sem prometer suporte universal. |
| Webapps | Preferências por perfil para downloads e acesso às permissões nativas de notificações, câmera e microfone; escolha de perfis para iniciar com a sessão e tratamento de links externos. Preservar favicons, diretórios, cookies e seleção de múltiplos perfis. |
| Proteção e atualização | Mostrar último backup e ponto de restauração bem-sucedidos, disponibilidade do destino e espaço restante. Verificações antes de atualizar e acompanhamento da validade de certificados e índices no servidor PHP. Documentar renovação e retorno após falha. |
| Resolução guiada | Fluxos para áudio, aplicativo que não abre, impressora e pasta de rede, com diagnóstico, ação e resultado. Completar abertura no Explorador e reconexão SMB após reinício ou perda de rede. |
| Consistência visual e acessibilidade | Navegação por teclado, foco visível, texto ampliado, telas pequenas, mensagens em português e aplicativos padrão consistentes. Preservar escolhas de aparência, idioma, teclado e energia das contas existentes. |

## Funcionalidades adicionais

As funções nativas já disponíveis devem ser integradas e apresentadas de forma consistente, sem ser anunciadas como uma implementação nova quando apenas ganharam um acesso mais fácil.

- **Busca unificada:** encontrar aplicativos, configurações e arquivos pelos termos usados no Windows e em português. Exibir o tipo e a localização do resultado, respeitar permissões e oferecer controle de indexação e exclusão de pastas.
- **Programas que iniciam com o sistema:** lista centralizada com origem e estado, ativação/desativação reversível por usuário e acesso ao diagnóstico. Diferenciar lançadores da sessão, processos em segundo plano e serviços do sistema; não prometer medir impacto sem dados reais.
- **Cópias e conflitos de arquivos:** aproveitar a fila nativa de transferências, com progresso e opções claras de substituir, manter ambos, comparar ou ignorar. Mostrar falhas parciais, destino desconectado e espaço insuficiente; oferecer pausa quando o backend suportar.
- **Aplicativos padrão e Abrir com:** escolher programa por extensão/tipo, testar a associação e desfazer a alteração, integrando programas Linux, aplicativos Windows registrados e destinos web compatíveis.
- **Armazenamento e limpeza:** apresentar categorias de espaço e prévia do que será removido. Limpar cache e lixeira por seleção explícita; tratar cookies, perfis web, documentos, ambientes Wine e backups separadamente.

## Validação e distribuição

A conclusão exige os fluxos reais da janela de propriedades, importação de documentos, instalação e remoção de aplicativos, duas sessões web independentes, uso de compartilhamento, backup/restauração e atualização 0.7 → 0.8 com dados e preferências preservados. A implantação deve registrar os componentes testados e seus limites, além dos logs, hashes e evidências visuais da imagem final.

Manter UEFI como fluxo principal, desktop de teste em 1280×768 e validação BIOS ao final. Testes físicos de processadores e periféricos permanecem adiados conforme orientação vigente. Resultados em laboratório não devem ser descritos como homologação de equipamentos indisponíveis. A condição Beta depende das validações efetivamente concluídas.

As imagens, os pacotes e os registros da 0.7 permanecem preservados. A 0.8 usa identificação e artefatos próprios; resultados pendentes não são tratados como aprovados.

## Referências técnicas

Consultadas em 3 de novembro de 2026:

- [Diálogo nativo de propriedades KIO/KDE](https://api.kde.org/kpropertiesdialog.html).
- [Extensão de compartilhamento no Debian 13](https://packages.debian.org/trixie/kdenetwork-filesharing).
- [Permissões e ACL POSIX](https://man7.org/linux/man-pages/man5/acl.5.html).
- [ACL Windows](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-lists).
- [Compatibilidade Proton e limitações por título](https://partner.steamgames.com/doc/steamhardware/proton).
- [Base de unidades e integração com o Explorador](ETAPA3-DRIVE-MANAGER.md).
- [Programas Windows e Loja na 0.7](COMPATIBILIDADE-0.7.md).
- [Perfis web na 0.7](WEBAPPS-0.7.md).
- [Rede e autenticação na 0.7](REDES-SOBRE-0.7.md).
- [Recuperação na 0.7](RECUPERACAO-0.7.md).
