# Linux BR — identidade geométrica

A fonte é `source/reference.svg`, fornecida pelo usuário. A seta, o semicírculo recortado, a estrela e as três cores foram preservados. O símbolo foi centralizado em uma área quadrada para uso em aplicativos; a versão monocromática usa recortes transparentes para manter a estrela e a separação do círculo.

## Entregáveis

- `overview.png` e `overview.svg`: apresentação da família visual.
- `../packages/linuxbr-branding/files/usr/share/linuxbr/identity/`: símbolos colorido/branco/grafite, assinaturas horizontais e cinco ícones; SVG editável e PNG transparente.
- `../packages/linuxbr-branding/files/usr/share/icons/hicolor/`: ícones nos tamanhos 16, 22, 24, 32, 48, 64, 128, 256 e 512, além de SVG escalável e simbólico.
- `../packages/linuxbr-branding/files/usr/share/wallpapers/LinuxBR-{graphite,light,forest,violet}/`: quatro wallpapers em SVG e PNG 3840×2160.
- `legacy/`: logo LB e wallpaper SVG anteriores. Pinguim e fotografias continuam nos arquivos da coleção.

## Uso

Grafite é o padrão do desktop e SDDM e fornece o fundo de Calamares/GRUB/ISOLINUX. Plymouth usa o símbolo colorido sobre fundo sólido e animação amarela. O menu usa `linuxbr`; o instalador usa `linuxbr-installer`. Os ícones `linuxbr-system`, `linuxbr-files` e `linuxbr-updates` são recursos para aplicações futuras, não novas aplicações implementadas nem substituições dos ícones de terceiros.

As assinaturas usam Noto Sans. Os PNGs são exportados com essa fonte; para editar os SVGs em outra máquina, instale Noto Sans. As cores originais são acentos; os fundos neutros dão contraste e espaço para trabalho. Prefira a assinatura colorida em fundo claro e a branca em fundo escuro. Não distorça a proporção do símbolo.

A arte vetorial foi criada diretamente a partir da referência, sem geração por IA de bitmap ou imagens externas. As exportações 4K são renderizações nativas dos vetores. Nenhuma licença externa das fotografias é atribuída a essa identidade: a origem do desenho é o SVG fornecido pelo usuário; a licença de distribuição da marca deve ser definida pelo projeto.

## Reproduzir

```bash
python3 scripts/generate-branding.py
python3 scripts/branding-overview.py
podman run --rm --security-opt label=disable \
  -v "$PWD:/src:rw" -w /src docker.io/library/debian:trixie bash -c \
  'apt-get update -qq && apt-get install -y --no-install-recommends librsvg2-bin fonts-noto-core && bash scripts/render-branding.sh && rsvg-convert -o branding/overview.png branding/overview.svg'
```

Os PNGs são versionados com o projeto. Esse passo de criação da identidade não é necessário para cada build da ISO. O gerador não modifica os wallpapers fotográficos ou o pinguim, nem o desktop do host.

### Compatibilidade com o renderizador Qt

A marca colorida representa o círculo recortado do SVG original com dois caminhos: preenchimento de semicírculo e arco branco. Não usa `clipPath` para essa geometria, evitando que Qt SVG desenhe o círculo além da borda esquerda. As coordenadas, cores e estrela da referência são preservadas; o deslocamento horizontal apenas centraliza a silhueta no quadro. `tests/test-branding-logo.py` compara a renderização Qt com o SVG original renderizado por librsvg, permitindo somente diferenças de rasterização.

## Superfícies sólidas e vidro

A paleta `LinuxBRClean` usa fundo claro, texto grafite e destaque violeta escuro
(`#6054A3`). Os tons pastel da logo continuam reservados à identidade. As áreas
de leitura e edição são opacas; o painel do Plasma usa translucidez nativa e
desfoque do KWin, sem painel flutuante. O efeito depende do compositor; não se
aplica transparência global às janelas.

Os quatro wallpapers 4K usam planos sólidos e diagonais discretas, sem degradês.
A geometria da logo é preservada; os blocos dos ícones passam a ter cantos de
12 unidades em 256 (antes 52). A Central usa navegação reta com uma linha de
destaque; as barras de unidades acompanham a cor de destaque do sistema.

As configurações são padrões de distribuição em `/etc/xdg` e no tema global.
Preferências pessoais existentes têm prioridade. O layout só configura o painel
na criação inicial. Para uma conta já personalizada, selecione Linux BR Clean
em Configurações do Sistema → Cores e ajuste o painel para translúcido.

Referência da API Plasma 6.3: https://github.com/KDE/plasma-workspace/blob/Plasma/6.3/shell/scripting/panel.cpp
