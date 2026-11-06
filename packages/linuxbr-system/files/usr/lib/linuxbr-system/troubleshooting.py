"""Bounded native diagnostics; changes remain explicit user actions."""
import shutil
from protection_status import command

PROBLEMS = {
    'Login e senhas dos aplicativos': {
        'checks': [('Armazenamento seguro da sessão', ['linuxbr-credentials', '--check', '--probe'])],
        'actions': [('Desbloquear o cofre de credenciais', ['linuxbr-credentials', '--unlock'], 'wallet-open'),
                    ('Gerenciar senhas e cofres', ['seahorse'], 'dialog-password')],
        'help': 'O retorno de um login Microsoft pode abrir o Bottles para entregar a autenticação ao programa Windows. O cofre precisa estar disponível e desbloqueado para lembrar a conta. Use o desbloqueio seguro; se a senha do usuário foi redefinida por um administrador, o cofre pode continuar usando a senha anterior. Não apague cofres que contenham senhas. Uma entrada bem-sucedida não comprova a ativação da licença do aplicativo.'},
    'Som e microfone': {
        'checks': [('Servidor de áudio', ['pactl', 'info']), ('Saídas de som', ['pactl', 'list', 'short', 'sinks']),
                   ('Entradas de som', ['pactl', 'list', 'short', 'sources'])],
        'actions': [('Ajustar saídas, microfone e volumes', ['linuxbr-system', '--page', 'Áudio'], 'audio-volume-high'),
                    ('Configurar Bluetooth', ['kcmshell6', 'kcm_bluetooth'], 'preferences-system-bluetooth')],
        'help': 'Confira a saída padrão, o volume do aplicativo e o microfone selecionado. Em headsets Bluetooth, o perfil de chamadas pode reduzir a qualidade do som.'},
    'Impressora': {
        'checks': [('Serviço de impressão', ['lpstat', '-r']), ('Impressoras e estado', ['lpstat', '-p', '-d'])],
        'actions': [('Gerenciar impressoras e imprimir teste', ['kcmshell6', 'kcm_printer_manager'], 'printer'),
                    ('Abrir fila de impressão', ['kde-print-queue'], 'document-print')],
        'help': 'Confira se a impressora está ligada e conectada por USB ou à mesma rede. Abra a impressora para revisar a fila e imprimir uma página de teste.'},
    'Rede e pastas compartilhadas': {
        'checks': [('Conectividade registrada', ['nmcli', 'general', 'status']),
                   ('Dispositivos de rede', ['nmcli', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device'])],
        'actions': [('Configurar rede', ['linuxbr-system', '--page', 'Rede'], 'network-wireless'),
                    ('Reconectar unidade de rede', ['linuxbr-drive-manager'], 'folder-network'),
                    ('Abrir senhas de rede', ['kwalletmanager5'], 'wallet-open')],
        'help': 'Informe a conta do computador que compartilha a pasta. Confira rede ou VPN, endereço, nome do compartilhamento e permissões. O cofre precisa estar desbloqueado para reutilizar senhas salvas.'},
    'Programa Windows não abre': {
        'checks': [('Versão do Wine', ['wine', '--version']), ('Ambientes gráficos disponíveis', ['vulkaninfo', '--summary'])],
        'actions': [('Diagnosticar programa na biblioteca', ['linuxbr-windows', '--page', 'library'], 'application-x-ms-dos-executable'),
                    ('Receitas e configuração Windows', ['linuxbr-windows', '--page', 'install'], 'applications-games')],
        'help': 'Selecione o programa na biblioteca e abra o diagnóstico. Confira arquitetura, ambiente e receita. Uma falha de Vulkan não comprova a causa da falha do programa; jogos precisam de avaliação individual.'},
}


def diagnose(problem):
    if problem not in PROBLEMS: raise ValueError('Selecione uma categoria de problema.')
    results = []
    for title, argv in PROBLEMS[problem]['checks']:
        if not shutil.which(argv[0]):
            results.append({'title': title, 'status': 'unavailable', 'output': 'Ferramenta não instalada: ' + argv[0]})
            continue
        code, output, error = command(argv, timeout=8)
        results.append({'title': title, 'status': 'completed' if code == 0 else 'attention',
                        'code': code, 'output': (output.strip() + '\n' + error.strip()).strip() or 'Nenhuma informação retornada.'})
    return {'problem': problem, 'results': results, 'help': PROBLEMS[problem]['help']}
