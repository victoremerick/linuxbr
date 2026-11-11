# Linux BR 1.1 Alpha 1

Pré-lançamento para avaliação da versão 1.1, com base Debian 13 e desktop Plasma para computadores `amd64`.

- **Atualizações em ondas.** O serviço da organização autoriza lotes APT assinados, permite começar pelo piloto e respeita pausa e janela de manutenção. O painel diferencia autorização, instalação concluída, falha e restauração.
- **Diagnóstico e recuperação.** A Central prepara diagnósticos por categoria com revisão antes do envio à TI. Atualizações gerenciadas usam pontos de recuperação, e a mídia Live oferece restauração guiada para os cenários compatíveis.
- **Preparação para trabalho ou escola.** A tela consulta o perfil assinado da organização, aplica preferências da conta e permite administrar o acesso às fontes Snap e Homebrew na Loja.
- **Loja.** As fontes opcionais incluem Snap Store e fórmulas Homebrew Core. A biblioteca exporta a lista de aplicativos para revisão e reinstalação, com indicação dos formatos e origens já testados.
- **Sessão gráfica.** A imagem inclui a correção Debian do KWin para uma queda ao desconectar ou reconectar monitores. [Registro da correção](https://bugs.debian.org/1150678)

Baixe todas as partes da ISO, confira os checksums e reúna os arquivos antes de gravar a mídia. Inicie em modo Live para conferir o funcionamento com seu equipamento. A validação automatizada desta Alpha cobre a inicialização Live. Instalação completa, primeiro login em Plasma Wayland, compartilhamento do monitor inteiro e compatibilidade em hardware físico são etapas de homologação separadas.

O serviço de ondas e perfis é instalado pela própria organização. As regras disponíveis nesta Alpha cobrem o recorte descrito nas notas e na documentação do projeto. [Documentação de manutenção](https://github.com/victoremerick/linuxbr/blob/v1.1.0-alpha1/docs/MANUTENCAO-1.1.md)
