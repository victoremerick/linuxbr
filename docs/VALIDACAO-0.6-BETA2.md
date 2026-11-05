# Validação da 0.6 Beta 2

Imagem: `linuxbr-0.6.0~beta2-amd64.iso`.

SHA256: `14d7a3a9fcca4b55e68592eafc9e86cc5c1236387d9b1eec3edd8653b2bdb16f`.

A consolidação incorporou os comandos familiares e BAT/CMD, além de ampliar a loja para consultar o registro de aplicativos do desktop. Writer, Calc e Impress foram verificados como entradas separadas.

Foram aprovadas 30 suítes de componentes, a instalação limpa UEFI, o primeiro login pelo disco instalado, a preservação de perfis e preferências na atualização e a correspondência dos arquivos instalados com os fontes congelados. A imagem usa desktop de 1280×768 nos testes.

O 7-Zip 26.05 para Windows foi instalado e usado para criar e verificar um arquivo. O OpenTTD 15.3 para Windows criou, salvou e reabriu uma partida. Também foram verificados documentos ODT/DOCX/PDF, perfis Chromium isolados e persistentes, restauração de uma versão anterior de documento e o repositório APT assinado em ambiente local.

O relatório detalha cada teste, as versões, capturas, correções durante a validação e as limitações: [relatório da Beta 2](../../reports/0.6-beta2/RELATORIO.md).

A publicação HTTPS depende da definição do servidor. A homologação em computadores físicos, periféricos e jogos Steam/Proton permanece pendente. A versão continua Beta.
