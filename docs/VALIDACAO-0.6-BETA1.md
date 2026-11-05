# Validação da 0.6 Beta 1

Data: 1 de novembro de 2026. Versão de pacote: `0.6.0~beta1`.

ISO: `linuxbr-0.6.0~beta1-amd64.iso`, 3.559.587.840 bytes.

SHA256:

```text
009d34664d40c52e68f8fdf539b723a51310153f42326f22f7f32e50c3e8ac39
```

## Resultados

- Build completo, integridade da ISO e cópia local com checksum correspondente.
- 28 suítes de componentes aprovadas; verificação adicional dos mapas de console e XKB.
- Instalação UEFI em disco virtual de 40 GiB, verificação da raiz instalada somente para leitura, reinício e autenticação na sessão Wayland.
- Desktop em 1280×768; kernel 6.12.113+deb13-amd64.
- Teste final de boot Live em BIOS legado, confirmado pela ausência de /sys/firmware/efi. Não foi feita instalação em BIOS.
- EXE x64, EXE x86 e MSI executados com sucesso na instalação atualizada e na instalação limpa da ISO final.
- Dois perfis Chromium simultâneos com cookies e armazenamento local separados e persistentes após reiniciar o navegador. Chromium 156.0.8078.73-1~deb13u1 na imagem final.
- Atualização 0.5 → 0.6 em disco de teste separado, preservando arquivos, preferências, perfis, favorito e progresso inicial, inclusive após reiniciar.
- Confirmação e cancelamento da exclusão seletiva de perfil fictício; criação de ambiente Windows pela interface.
- Tradução compilada do instalador verificada e resumo da instalação com fuso e modelo completos.
- Repositório assinado com os 12 pacotes finais aceito pelo APT; índices adulterados rejeitados. Teste isolado, com chave temporária descartada.

## Teclado brasileiro

O padrão é modelo pc105 e layout br, que contém o ABNT2 no xkb-data 2.42. Foram conferidos ç/Ç, acentos, barra, interrogação, contrabarra e composição de á/ã/ê. O identificador antigo de modelo abnt2 não consta do registro de modelos dessa versão. A identificação pc105 observada na 0.5 não representa, por si só, perda do layout ABNT2.

## Evidências e alcance

Os registros completos e os arquivos de entrada ficam em `.cache/evidence/0.6-beta1/` na máquina de build. O pacote `linuxbr-0.6-beta1-evidencias.zip` reúne relatório, capturas, resultados e logs públicos. Senhas, chaves privadas, perfis de navegador e registros brutos privados não fazem parte da entrega.

O relatório distingue os testes da atualização e os executados na instalação limpa da ISO final. Ferramentas de diagnóstico foram acrescentadas somente à VM, após verificar a instalação original. O servidor SSH de diagnóstico não integra a instalação original da ISO.

Não houve teste de hardware físico, GPU dedicada, impressoras, scanners, Bluetooth, pendrives reais ou contas autenticadas de serviços externos. Os testes Wine não representam compatibilidade universal com programas, drivers ou sistemas antitrapaça. A versão permanece Beta.

A publicação e a ativação do repositório próprio dependem da definição da hospedagem HTTPS e da distribuição confiável da chave. Nenhuma fonte fictícia foi habilitada nos computadores.
