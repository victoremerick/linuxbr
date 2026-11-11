# Validação da ISO 1.1 Alpha 1

Execute a compilação, os testes e a preparação do GitHub Release no host remoto ou no runner Linux que guarda a ISO. Use o mesmo arquivo gerado pelo checkout de `1.1.0~alpha1`. As capturas e os relatórios identificam esse arquivo pelo SHA-256.

## Verificações automatizadas

Execute a validação no checkout que compilou a imagem.

```bash
ISO="$PWD/dist/linuxbr-1.1.0~alpha1-amd64.iso" \
  QA_EVIDENCE_BASE="$PWD/.cache" bash tests/qa-release-iso.sh headless
```

O comando usa o checksum do build e verifica as entradas El Torito de UEFI e BIOS. Depois inicia a ISO original em QEMU, em UEFI primeiro e em BIOS por último. Cada VM usa 4 GiB de RAM, VGA com EDID de 1280×768 e somente a mídia óptica. O modo headless usa KVM quando acessível e TCG nos demais casos.

O monitor QMP captura a tela e usa Tesseract para localizar o menu, o login e o terminal. A aprovação exige que o próprio guest confirme no serial a sessão Live, o firmware esperado, a versão exata do pacote `linuxbr-release`, o SDDM ativo e o Plasma iniciado. O runner grava capturas PPM, logs e um JSON por firmware, vinculados ao hash original. Falhas de navegação ou ausência de confirmação produzem saída diferente de zero e preservam as evidências já coletadas. [QEMU QMP](https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html)

No Debian ou Ubuntu, instale previamente `qemu-system-x86`, `ovmf`, `tesseract-ocr`, `tesseract-ocr-eng`, `xorriso`, `file` e `python3`. Use o modo `integrity` para executar apenas as verificações de arquivo e catálogo de boot.

## Instalação e sessão gráfica

Para acompanhar no próprio host, execute o modo `interactive` com `qemu-img` e o backend gráfico do QEMU. Para VNC, use o endereço local do host remoto e um túnel SSH. [QEMU VNC](https://www.qemu.org/docs/master/system/invocation.html)

```bash
# No host que guarda a ISO
QEMU_DISPLAY=vnc=127.0.0.1:5 \
  ISO="$PWD/dist/linuxbr-1.1.0~alpha1-amd64.iso" \
  bash tests/qa-release-iso.sh interactive

# Em um terminal separado, para abrir o visualizador VNC no cliente
ssh -N -L 5905:127.0.0.1:5905 HOST-REMOTO
```

Abra o visualizador em `127.0.0.1:5905`. O roteiro usa os lançadores existentes e guarda o disco e a NVRAM UEFI na pasta da execução. Cada desligamento passa à próxima VM.

1. Inicie o Desktop Live em UEFI, entre com a conta temporária `user` e confira a sessão em 1280×768. No terminal, confira `test -d /run/live/medium`, `test -d /sys/firmware/efi` e `dpkg-query -W linuxbr-release`. Abra o Calamares, selecione Desktop e instale no disco virtual novo. Guarde a captura de conclusão e desligue a VM.
2. Inicie pelo disco UEFI e entre na conta criada. Confira o firmware, a versão de `linuxbr-release` e `findmnt /`. Abra a Loja, a Central do Sistema e o assistente de recuperação. Guarde as capturas e os resultados da sessão instalada.
3. No primeiro login, compartilhe o monitor inteiro usando a página de teste. Repita após mudar a resolução e após sair e entrar na sessão. Quando o ambiente permitir, desconecte e reconecte uma saída e repita a captura.
4. Desligue a VM instalada. Inicie o Desktop Live em BIOS na última etapa, confira a versão, `/run/live/medium` e a ausência de `/sys/firmware/efi`. Guarde a captura e desligue a VM. O roteiro confere novamente o SHA-256 da ISO.

O encerramento do QEMU registra o fim de uma sessão. Use as observações e capturas do guest para aprovar a instalação e as funções do desktop.

### Compartilhamento do monitor

Sirva `tests/fixtures/screen-sharing.html` do host pelo endereço local do QEMU e copie a página para a conta de teste. Na sessão instalada, sirva a página pelo endereço de loopback do guest.

```bash
# No host remoto
python3 -m http.server 8891 --bind 127.0.0.1 --directory tests/fixtures

# No terminal da sessão instalada
mkdir -p "$HOME/qa-screen"
curl --fail --silent --show-error http://10.0.2.2:8891/screen-sharing.html \
  --output "$HOME/qa-screen/screen-sharing.html"
python3 -m http.server 8891 --bind 127.0.0.1 --directory "$HOME/qa-screen"
```

No Chromium, abra `http://127.0.0.1:8891/screen-sharing.html`, maximize a janela e selecione o monitor inteiro no seletor. Guarde o resultado `PASS` com `displaySurface` igual a `monitor` e `distinctColors` igual a `2`. Após novo login, inicie novamente o servidor da página se o processo anterior tiver encerrado. Consulte os cenários de compartilhamento da [versão 1.1](VERSAO-1.1.md).

## GitHub Actions e publicação

Use um runner Linux x64 dedicado ou um larger runner com espaço para o Podman, os intermediários, a ISO e a preparação do upload. O build confere 32 GiB livres no volume do checkout por padrão. A configuração padrão hospedada declara 14 GB de armazenamento. O build também precisa executar o contêiner privilegiado usado pelo live-build. [Runners do GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)

Execute o build, o roteiro e a preparação do lançamento no host que guarda a imagem. Uma execução `headless` aprova os dois boots Live e a integridade. Registre a instalação e o compartilhamento a partir da execução interativa da mesma imagem. Na publicação, use as notas e o checkout da compilação e compare o hash com as evidências. O utilitário do projeto cria o rascunho, marca Alpha como pré-lançamento e gera os hashes do arquivo original e das partes enviadas. [Publicação no GitHub](PUBLICACAO-GITHUB.md)
