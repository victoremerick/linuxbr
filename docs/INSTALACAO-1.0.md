# Instalação e primeiros passos — Linux BR 1.0

Estado deste guia: candidata RC 2. Confira o relatório que acompanha a ISO para saber quais cenários foram executados nessa mídia.

## Preparar a mídia

1. Obtenha a ISO, `SHA256SUMS`, sua assinatura e a chave pública pelo canal do projeto. Confira a impressão digital da chave por um canal conhecido.
2. No Windows, calcule o hash com `Get-FileHash -Algorithm SHA256 caminho-da-ISO`. Compare os 64 caracteres com a linha correspondente em `SHA256SUMS`. A assinatura do manifesto permite conferir a autoria dos checksums.
3. Grave a imagem em um pendrive destinado ao Linux BR. A ferramenta de gravação deve mostrar a unidade escolhida e pedir confirmação para substituir seu conteúdo.
4. Abra o menu de inicialização do computador e escolha o pendrive. Para uma instalação UEFI, escolha a entrada UEFI da mídia.

## Experimentar e instalar

A sessão temporária da mídia usa a conta `user` e a senha `live`. O menu oferece Desktop, Servidor e opções de manutenção. Na instalação, crie sua conta e escolha uma senha própria.

O Desktop oferece a área de trabalho completa. O Servidor abre um console gráfico mínimo para administrar rede, contas, serviços, armazenamento e máquinas virtuais.

Abra **Instalar Linux BR**. Confira idioma, teclado, edição, disco e resumo antes de iniciar. Use um disco de testes ou uma unidade destinada ao sistema. A gravação da instalação ocorre somente após a confirmação apresentada pelo instalador. Confira o backup dos seus arquivos antes de escolher opções de particionamento.

A matriz de suporte identifica os cenários de inicialização, Secure Boot, criptografia e convivência com outros sistemas que receberam homologação. Instalações em equipamentos e configurações fora dessa matriz permanecem experimentais.

## Primeiro acesso

Abra **Preparar meu computador** para conferir sua conta, arquivos, rede, idioma, tela, dispositivos, tarefas do dia a dia, backup, atualizações e aplicativos. **Conferir estado atual** faz uma consulta local. **Já conferi esta etapa** registra a sua revisão; é possível fechar e retomar depois.

Na **Loja Linux BR**, procure aplicativos, escolha categorias, consulte a origem e revise a instalação. **Fontes** reúne os repositórios configurados. **Downloads e histórico** mostra as operações. Durante uma transação DEB, o botão de cancelamento acompanha a permissão do gerenciador; algumas etapas precisam terminar para preservar a consistência dos pacotes.

Em **Programas Windows e jogos**, consulte as receitas e os cenários efetivamente testados. Cada resultado identifica a versão do aplicativo e a versão do Linux BR. Escolha um ambiente separado quando programas precisarem de configurações diferentes.

Os aplicativos web mantêm contas em perfis próprios. Um perfil salvo abre diretamente; com vários perfis, escolha um ou mais para abrir. Use **Novo perfil** para uma sessão independente do mesmo serviço. A atualização dos metadados preserva os perfis locais.

## Atualizar e recuperar

Abra **Loja Linux BR → Atualizações** e atualize os índices antes de revisar os pacotes. Confira espaço livre, energia e o destino de recuperação. Os registros da operação ficam no histórico.

Os snapshots registram o sistema; os planos de backup pessoal guardam versões dos documentos. Confira o destino e experimente restaurar um arquivo após configurar o primeiro backup.

Para manutenção, use **Shift + Reiniciar** ou as opções avançadas do menu de inicialização. Há modos de segurança, terminal, vídeo básico e diagnóstico. A recuperação solicita autenticação e oferece restauração, reparo de menu, terminal e retorno à inicialização normal.

Consulte também [Servidor e recuperação](SERVIDOR-RECUPERACAO-0.9.md), [terminal e arquivos BAT](TERMINAL-WINDOWS-BAT.md), [máquinas virtuais](MAQUINAS-VIRTUAIS-0.8.5.md) e [propriedades dos arquivos](PROPRIEDADES-0.8.md).
