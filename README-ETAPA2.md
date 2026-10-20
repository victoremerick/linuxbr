> Documento histórico da versão 0.2. Para a versão atual, consulte README.md. Não reaplique o patch.

# Linux BR 0.2 Alpha — personalização inicial

Este pacote é um **patch para aplicar sobre o repositório Linux BR existente**, não uma ISO.

1. Extraia o ZIP **na raiz** de `~/git/linuxbr`.
2. Execute `./apply-stage2.sh` e confira `git diff`.
3. Encerre qualquer VM ou build em execução. Antes de remover a pasta `build/`, confirme que não há montagens ativas (`findmnt -R build`).
4. Se não houver montagens, execute `sudo rm -rf -- build/` para forçar a reconstrução das configurações do chroot.
5. Execute `sudo env CONTAINER_ENGINE=podman ./build.sh`.
6. Verifique `cd dist && sha256sum -c SHA256SUMS` e teste com QEMU.

## Escopo

- Adiciona metadados próprios em `/etc/linuxbr-release` e banner em `/etc/issue`.
- Adiciona wallpaper SVG e autostart global KDE para aplicá-lo quando a sessão abrir.
- Atualiza o nome da ISO para `linuxbr-0.2-amd64.iso`.
- Garante pacote do kernel e remove nome antigo inválido do gerenciador de partições.
- Preserva `/etc/os-release` do Debian para compatibilidade.

## Limitações

- Não altera ainda Calamares, SDDM, GRUB ou Plymouth.
- O wallpaper depende do comando `plasma-apply-wallpaperimage` estar disponível e da sessão KDE permitir a alteração; teste no Live e no sistema instalado.
- O pacote ainda não foi compilado em Fedora/Podman nesta sessão; valide o resultado antes de publicar.
- A instalação do sistema não deve ser feita em disco com dados importantes.
