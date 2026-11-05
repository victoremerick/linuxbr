# Linux BR 0.6 Beta 1

A versão 0.6 concentra as tarefas de instalação, contas de aplicativos e uso diário. A base continua Debian 13, KDE Plasma e Chromium, com Wine para programas Windows e Steam/Proton para jogos compatíveis.

## Loja

- Explorar catálogo e Meus aplicativos, com busca e filtros por tipo.
- Aplicativos Linux disponíveis no catálogo, todos os perfis web ativos e atalhos Windows registrados.
- Abertura direta do perfil ou programa escolhido, sem criar outra instalação.
- Remoção de atalhos com confirmação, preservando o programa e seus dados.
- Acesso separado às atualizações e à lista completa de pacotes do Discover, que mantém a autorização e confirmação de instalação/desinstalação.

## Instalação Windows

Abrir / instalar apresenta o arquivo, a arquitetura detectada e a escolha entre um novo ambiente recomendado ou um ambiente existente. A criação e a execução acontecem somente após confirmar. Um arquivo x64 não pode usar um ambiente win32. EXE/MSI continuam sendo executados sem sudo; ajustes separados não constituem isolamento de segurança.

Depois de instalar, Localizar instalados permite selecionar os executáveis e adicionar atalhos à biblioteca e ao menu. A desinstalação fica no ambiente correspondente. Programas que dependem de drivers Windows e determinados sistemas antitrapaça podem não funcionar.

## Contas web

Uma conta continua abrindo diretamente. Com várias contas, a caixa de seleção aparece no centro de uma tela dedicada, inclusive no Wayland, e o perfil preferido fica marcado inicialmente, permitindo escolher uma ou mais contas. Remover do menu mantém cookies e dados. Apagar dados permite escolher inclusive um perfil oculto, exige confirmação e bloqueia a exclusão se houver um arquivo de bloqueio do Chromium. Perfis e diretórios simbólicos externos não são percorridos para apagar dados.

## Uso diário e primeiros passos

A Central inclui Uso diário: pendrives/NTFS, pastas Windows na rede, impressoras, som/Bluetooth, aplicativos padrão e leitura/teclado. Os botões abrem os serviços nativos. As orientações explicam remoção segura, discos Windows somente para leitura, permissões SMB, IPP e perfis de headset. O assistente inicial tem oito etapas, mantém o progresso pessoal e oferece um campo para experimentar acentos e teclas.

## Instalador e empacotamento

A imagem usa o layout br, que contém o ABNT2, com o modelo pc105 reconhecido pelo registro XKB atual. A mesma configuração é gravada em /etc/default/keyboard e na configuração X11 consultada pelo serviço locale1. O antigo identificador de modelo abnt2 não consta da lista de modelos do xkb-data 2.42; a disposição brasileira permanece no layout br. As escolhas feitas no instalador continuam válidas. A tradução local preserva os marcadores de modelo de teclado e fuso horário que estavam ausentes no Calamares 3.3.14. O build recupera permissões executáveis de scripts a partir do cabeçalho, incluindo quando as fontes são transportadas pelo Windows.

## Atualizações próprias

`scripts/build-repository.py` produz pool, Packages, índices comprimidos, Release com validade de 14 dias, InRelease e assinatura destacada. Usa uma chave externa ao repositório de fontes, exporta somente a chave pública e rejeita saída existente para preservar publicações anteriores. Restringe a entrada aos pacotes Linux BR e Dolphin customizado.

Com um endereço HTTPS, gera também a fonte deb822 com Signed-By específico. O arquivo de prioridades fica restrito aos nomes de pacotes da distribuição. Não adiciona fontes aos computadores automaticamente. A publicação pública e a ativação nos clientes dependem da hospedagem e da distribuição confiável da chave. Consulte REPOSITORIO-ATUALIZACOES.md.

## Validação

Os resultados efetivamente executados, imagens, versões e limitações ficam no relatório de validação da versão. A condição de Beta permanece até concluir instalação e atualização em equipamento físico, periféricos e os programas reais usados pelo público.

A validação de teclado usa libxkbcommon para verificar ç/Ç, teclas de acento, barra, interrogação, contrabarra e composição de á/ã/ê. O teste automatizado não substitui a verificação de um teclado físico. Referências: [modelos do Debian](https://manpages.debian.org/trixie/xkb-data/xkeyboard-config.7.en.html) e [explicação da unificação dos modelos pelo mantenedor](https://blogs.gnome.org/sudaltsov/2009/02/26/national-specific-models-so-long/).
