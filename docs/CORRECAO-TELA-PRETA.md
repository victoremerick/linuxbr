# Correção da transição Plymouth → SDDM

Em 15/10/2026, a instalação BIOS da versão 0.3.0 foi diagnosticada via QMP. O kernel executava, mas a tela permanecia preta e o Xorg parava durante a abertura do display pelo SDDM. A falha foi reproduzida tanto com virtio-vga quanto com VGA.

O override de `plymouth-quit.service` usava `plymouth quit --retain-splash`, introduzido para preservar a imagem durante a transição. Remover esse argumento na sessão snapshot restaurou a tela de login. A mesma correção foi então aplicada no disco instalado e confirmada em boot normal com virtio-vga, sem `nomodeset` ou modo de recuperação.

O pacote linuxbr-boot-theme agora usa `ExecStart=-/usr/bin/plymouth quit`, liberando o terminal para o servidor gráfico. Logo, animação Plymouth, splash Plasma e ocultação de mensagens continuam configurados. A transição pode ter um breve apagamento; não se mantém um terminal gráfico retido para esconder essa troca.

`tests/test-packages.py` e `tests/check-rootfs.py` verificam o encerramento normal do Plymouth e rejeitam `--retain-splash` nesse override. O build utiliza o pacote corrigido automaticamente; executar `./init-build.sh` gera a próxima ISO com a correção. Imagens já existentes em dist não são alteradas.

Na instalação reparada, o backup do override ficou em `/etc/systemd/system/plymouth-quit.service.d/linuxbr.conf.before-fix`; o sufixo não é carregado pelo systemd. O disco é `vm/linuxbr-0.3.0-bios.qcow2`. A captura do login após o reparo está em `.cache/vm-repair.gr1_q1xt/current.png`, e o diagnóstico anterior em `.cache/vm-diagnostic.7tl2X0/serial.log`.

Validação: boot real até SDDM em BIOS; testes de scripts e verificação do override. Login do usuário e boot UEFI não foram executados neste reparo. Não foi necessário trocar o driver de vídeo da instalação nem reinstalar o sistema.
