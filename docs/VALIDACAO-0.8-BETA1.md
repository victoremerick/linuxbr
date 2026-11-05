# Validação — Linux BR 0.8 Beta 1

Esta página descreve o alcance da validação da edição. Os resultados de cada execução, com horários, versões, hashes e capturas, acompanham a imagem no pacote `linuxbr-0.8-beta1-evidencias.zip`. O relatório desse pacote identifica a imagem efetivamente conferida e distingue testes de componentes, atualização e instalação limpa.

## Componentes já exercitados

- KIO recompilado da fonte Debian 6.13.0-6 com extensão aditiva para Aplicar; cinco pacotes de execução e hashes de origem e binários.
- Diálogo nativo de propriedades: duas suítes com Aplicar repetido, renomeação, permissões, seleção múltipla e comparação SHA-256/SHA-512.
- Backend de propriedades e duas versões reais de backup bup, restauradas em outro destino com conferência de integridade.
- Loja com instalação e remoção real do pacote Hello, incluindo autorização nativa; Flatpak em repositório privado assinado com instalação, recusa de atualização, atualização e remoção preservando dados pessoais.
- Ambiente Wine de laboratório com executável próprio: configuração, execução, reparação com cópia e nova execução, preservando os demais ambientes.
- Certificado e assinatura do repositório, incluindo renovação com a mesma autoridade e recusa de índices alterados.
- Chromium real com dois perfis simultâneos: cookies e armazenamento separados na mesma origem, persistência ao reabrir, downloads em destinos diferentes, preferências nativas e encaminhamento de links sem retorno ao mesmo aplicativo.
- Navegação por teclado e texto ampliado, incluindo Enter nas ações e retorno entre páginas internas sem conflito de atalhos.

## Conferências da distribuição

A conferência da distribuição abrange pacotes e fontes da imagem, atualização 0.7 → 0.8, propriedades e compartilhamento na sessão gráfica, perfis Chromium, importação pela interface, limpeza, inicialização UEFI e BIOS ao final. Os arquivos do pacote de evidências conservam o resultado de cada etapa; a existência deste documento não substitui esses resultados.

A resolução principal é 1280×768. Os testes de diferentes processadores físicos foram adiados por orientação do projeto. Periféricos, vídeo e suspensão em equipamentos físicos exigem homologação própria. Jogos Steam/Proton e serviços web dependem de cada título, conta, serviço e hardware; não há declaração de compatibilidade universal.
