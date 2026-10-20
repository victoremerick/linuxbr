#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
[[ ! -f VERSION ]] || { echo "Patch historico 0.2: nao reaplique sobre a versao atual." >&2; exit 1; }
[[ -f build.sh && -d config/package-lists ]] || { echo 'Execute na raiz do repositorio Linux BR.' >&2; exit 1; }
mkdir -p config/includes.chroot/etc config/includes.chroot/usr/share/linuxbr config/includes.chroot/usr/local/bin config/includes.chroot/etc/skel/.config/autostart config/package-lists
cat > config/includes.chroot/etc/linuxbr-release <<'EOF'
NAME="Linux BR"
VERSION="0.2 Alpha"
VERSION_ID="0.2"
BASE="Debian 13 (trixie)"
EOF
cat > config/includes.chroot/etc/issue <<'EOF'
Linux BR 0.2 Alpha (base Debian 13) \n \l
EOF
cat > config/includes.chroot/usr/share/linuxbr/wallpaper.svg <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#122e3b"/><stop offset="1" stop-color="#1a685e"/></linearGradient></defs>
<rect width="1920" height="1080" fill="url(#bg)"/>
<circle cx="1610" cy="160" r="460" fill="#ffffff" opacity=".035"/>
<circle cx="210" cy="1040" r="620" fill="#ffffff" opacity=".025"/>
<text x="115" y="525" font-family="sans-serif" font-size="130" font-weight="700" fill="#f5f5ed">Linux BR</text>
<text x="120" y="595" font-family="sans-serif" font-size="35" fill="#c2e3da">Livre para criar. Feito para o Brasil.</text>
<text x="120" y="980" font-family="sans-serif" font-size="24" fill="#b4d2cb">0.2 Alpha · Debian 13 · KDE Plasma</text>
</svg>
EOF
cat > config/includes.chroot/usr/local/bin/linuxbr-set-wallpaper <<'EOF'
#!/bin/sh
# Executa na sessao grafica do usuario; nao exige privilegios.
if command -v plasma-apply-wallpaperimage >/dev/null 2>&1; then
  plasma-apply-wallpaperimage /usr/share/linuxbr/wallpaper.svg >/dev/null 2>&1 || true
fi
EOF
chmod +x config/includes.chroot/usr/local/bin/linuxbr-set-wallpaper
cat > config/includes.chroot/etc/skel/.config/autostart/linuxbr-wallpaper.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Linux BR - Papel de parede inicial
Exec=/usr/local/bin/linuxbr-set-wallpaper
OnlyShowIn=KDE;
X-KDE-autostart-phase=2
NoDisplay=true
EOF
# live-config pode gerar usuario live depois da criacao da imagem: garantir autostart global tambem.
mkdir -p config/includes.chroot/etc/xdg/autostart
cp config/includes.chroot/etc/skel/.config/autostart/linuxbr-wallpaper.desktop config/includes.chroot/etc/xdg/autostart/linuxbr-wallpaper.desktop
# Evitar duplicacao para usuarios novos: usar apenas autostart global.
rm config/includes.chroot/etc/skel/.config/autostart/linuxbr-wallpaper.desktop
# Corrige lista antiga caso ainda contenha nome incorreto.
find config/package-lists -type f -name '*.list.chroot' -exec sed -i '/^kde-partitionmanager$/d' {} +
# Kernel obrigatorio para o live-build.
printf '%s\n' linux-image-amd64 live-boot live-config > config/package-lists/kernel.list.chroot
# Mudar nome da ISO e volume no script de build existente.
sed -i 's/LINUXBR_0_1/LINUXBR_0_2/g; s/linuxbr-0\.1-amd64\.iso/linuxbr-0.2-amd64.iso/g' scripts/build-in-container.sh
# Evitar adicionar arquivos de build ao Git.
cat >> .gitignore <<'EOF'
/build/
/dist/
/vm/
*.log
EOF
printf '\nEtapa 2 aplicada. Revise git diff antes de compilar.\n'
