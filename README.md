# Linux BR 0.1 — Live ISO (Debian 13 + KDE Plasma)

Projeto inicial de distribuição brasileira, baseada em Debian 13 (trixie), com KDE Plasma e Calamares. **Protótipo experimental**; não utilize em discos com dados importantes sem backup.

## Fedora: dependências

```bash
sudo dnf install -y podman qemu-system-x86 qemu-img edk2-ovmf
```

Os nomes dos pacotes Fedora podem variar por versão (por exemplo `qemu-img` pode fazer parte de `qemu-tools`). Recomenda-se pelo menos 30 GB livres, 8 GB RAM e internet estável.

## Construção

```bash
cd linuxbr
sudo env CONTAINER_ENGINE=podman ./build.sh
```

O build usa um container Debian **privilegiado**, pois o `live-build` usa mount/chroot. Execute apenas scripts que você confia. A primeira execução pode demorar e consumir vários GB. Resultado esperado:

```
dist/linuxbr-0.1-amd64.iso
dist/SHA256SUMS
```

**Nota:** o build é experimental e não foi executado/validado neste ambiente. Dependências ou configurações do Calamares podem exigir ajustes na primeira execução.

## Teste

```bash
./tests/verify-iso.sh
./tests/test-iso.sh bios
./tests/test-iso.sh uefi
```

Na VM, abra o Calamares pelo menu de aplicativos (a disponibilidade e o lançador dependem do pacote `calamares-settings-debian`). Instale no disco virtual de 32 GB, remova a ISO no teste posterior e confirme que o sistema instalado inicializa. Para testar o disco instalado, use:

```bash
qemu-system-x86_64 -m 4096 -smp 2 -drive file=build/test-disk.qcow2,format=qcow2,if=virtio -nic user,model=virtio-net-pci
```

## Organização

- `build.sh`: entrada do build no Fedora via Podman
- `scripts/build-in-container.sh`: live-build executado no Debian
- `config/package-lists/`: pacotes da ISO
- `config/includes.chroot/`: arquivos inseridos no sistema Live
- `tests/`: checagem de hash e inicialização em QEMU
- `build/`: arquivos temporários, ignorados pelo Git
- `dist/`: ISO e checksums, ignorados pelo Git

## Limitações da versão 0.1

- Ainda usa identidade do Debian em vários locais (não altera `/etc/os-release`, evitando quebrar detecção de base).
- Não inclui gerenciador próprio de letras, drivers ou AD; esses módulos serão projetos posteriores.
- Calamares precisa ser testado em BIOS e UEFI, incluindo instalação, particionamento e bootloader.
- Não existe repositório Linux BR próprio nem mecanismo próprio de assinatura de atualizações.
- Secure Boot não está homologado; não assuma que funciona em hardware com Secure Boot habilitado.
- `sudo`/container privilegiado e build não reproduzível byte a byte.

## Próximas etapas

1. Validar o build e corrigir quaisquer incompatibilidades de pacotes Debian.
2. Testar sessão Live, Calamares, instalação BIOS e UEFI e reboot sem ISO.
3. Empacotar branding e configurações em `.deb` próprios.
4. Automatizar smoke tests e instalar em hardware de laboratório.
5. Criar o Linux BR Central, começando por armazenamento e rede.
