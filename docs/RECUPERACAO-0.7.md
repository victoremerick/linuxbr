# Recuperação do sistema na versão 0.7

A Central utiliza o Timeshift para pontos de restauração dos arquivos e configurações do sistema. Em modo RSYNC, ele mantém cópias incrementais com arquivos compartilhados por links físicos. Documentos, fotos e demais dados das pastas pessoais ficam excluídos por padrão; faça o backup desses arquivos separadamente. A restauração pode ser iniciada no sistema instalado ou por um ambiente Live. [Documentação do Timeshift](https://github.com/linuxmint/timeshift).

## Configuração obrigatória do destino

Abra **Pontos de restauração**, escolha o modo **RSYNC** e selecione um destino com espaço suficiente antes de contar com a proteção automática. O serviço não escolhe ou formata um disco por conta própria. Uma partição separada permite manter os pontos fora da partição do sistema; confira o destino na interface do Timeshift. [Configuração e destino no Timeshift](https://github.com/linuxmint/timeshift#minimal-setup).

O serviço da versão 0.7 aceita somente a configuração RSYNC para a proteção durante atualizações e recusa filtros de inclusão pessoal. Não habilite a inclusão de dados de `/home` ou `/root` para essa finalidade. A escolha de BTRFS na interface do Timeshift não torna esse modo homologado para o serviço automático desta versão.

O pacote Timeshift utilizado pela distribuição está disponível nos repositórios do Debian. Sua interface também oferece criação e restauração manuais, com autenticação administrativa. [Pacote Timeshift no Debian](https://packages.debian.org/trixie/timeshift).

## Proteção antes de atualizar

O gancho `DPkg::Pre-Install-Pkgs` é chamado pelo APT antes de instalar os arquivos `.deb`. O protocolo de nomes de arquivos permite inspecionar os pacotes da transação; um código de saída de falha interrompe o APT antes da chamada correspondente ao dpkg. [Manual oficial apt.conf](https://manpages.debian.org/trixie/apt/apt.conf.5.en.html#HOW_APT_CALLS_DPKG(1)).

No LinuxBR, o serviço cria um ponto quando uma transação inclui uma versão mais nova de um pacote crítico já instalado: componentes LinuxBR, kernel, Plasma, KWin, libc6, systemd, APT ou dpkg. Ele não cria pontos para toda instalação de aplicativo, reinstalação da mesma versão, downgrade ou remoção. A instalação direta com `dpkg` não passa por esse gancho.

- No ambiente Live e durante a construção da imagem, o serviço ignora a operação.
- Sem destino configurado, a atualização continua, registra **não configurado** e apresenta uma orientação. Essa situação não oferece ponto de restauração automático.
- Se o administrador desativou a política, a operação registra **desativado**.
- Com destino configurado e política ativa, a atualização só continua após a criação bem-sucedida do ponto.
- Falha de criação, comando ausente, tempo limite, configuração existente inválida ou permissões inseguras fazem a proteção retornar erro e interromper a atualização correspondente.

Os arquivos de configuração exigem proprietário administrativo, sem permissão de escrita para grupo ou outros usuários e sem links simbólicos. O estado da última operação fica em `/var/lib/linuxbr/recovery/last.json`.

## Restauração e limites

Na interface do Timeshift, escolha o ponto, revise as partições e confirme a restauração. Se o sistema não iniciar, abra a ferramenta pelo ambiente Live e localize o destino dos pontos. A restauração do sistema em execução requer reinicialização. [Restauração no Timeshift](https://github.com/linuxmint/timeshift#system-restore).

A versão 0.7 não oferece recuperação automática pelo menu de boot nem trata o ponto como imagem integral do disco. O gancho não cobre Flatpak, Wine, instaladores externos ou alterações manuais. A presença de um ponto não comprova que todos os dispositivos e configurações de inicialização poderão ser recuperados; a verificação prática depende do armazenamento, das partições e do firmware utilizados.

## Testes de política

Os testes `tests/test-recovery-07.py` e `tests/test-update-status.py` usam diretórios temporários, proprietários de arquivos simulados e respostas de comandos controladas. Nenhum desses testes cria ou restaura pontos reais. Eles verificam as decisões da política, a propagação de falhas ao APT e a leitura de versões e reinicialização pendente.

```sh
python3 tests/test-recovery-07.py
python3 tests/test-update-status.py
```

O resultado da execução deve ser registrado no relatório de validação. Esses testes não substituem uma recuperação completa em uma instalação descartável, com falha simulada e conferência posterior dos arquivos do sistema e dos dados pessoais.
