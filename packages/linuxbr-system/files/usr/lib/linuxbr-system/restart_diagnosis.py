"""Summarize the preceding boot from evidence available to the current user."""
import json
import re

from support_diagnostics import query


JOURNAL = ('/usr/bin/journalctl', '--boot=-1', '--quiet', '--no-pager', '--output=json',
           '--output-fields=MESSAGE')
PANIC = re.compile(r'kernel panic|not syncing|fatal exception in interrupt', re.I)
SHUTDOWN = re.compile(
    r'^(?:Reached target System (?:Reboot|Power Off|Halt)|'
    r'Shutting down|Powering off|Rebooting|System is (?:rebooting|powering down))\b', re.I)


def messages(output):
    for line in (output or '').splitlines():
        try:
            text = json.loads(line).get('MESSAGE')
        except (ValueError, AttributeError):
            continue
        if isinstance(text, str):
            yield text


def classify(kernel, ending):
    if any(PANIC.search(message) for message in messages(kernel)):
        return ('Pane do kernel registrada',
                'O diário do boot anterior contém uma mensagem de falha fatal do kernel.')
    if any(SHUTDOWN.search(message) for message in messages(ending)):
        return ('Encerramento solicitado',
                'O diário registra que o sistema iniciou uma sequência normal de encerramento.')
    if not ending:
        return ('Histórico indisponível',
                'A conta atual não encontrou registros do boot anterior. Confira o diário do sistema na Central de Diagnóstico.')
    return ('Causa indeterminada',
            'O diário termina sem uma sequência de encerramento registrada. Falta de energia, travamento e perda dos últimos registros podem produzir esse resultado.')


def inspect():
    ending = query([*JOURNAL, '--lines=160'])
    kernel = query([*JOURNAL, '--dmesg', '--priority=err', '--lines=80']) if ending else ''
    return classify(kernel, ending)
