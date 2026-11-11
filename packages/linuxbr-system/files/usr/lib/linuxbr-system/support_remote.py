#!/usr/bin/python3
"""Restricted bridge from the support dialog to the organization's diagnostic API."""
import json
import os
import re
import sys

from support_diagnostics import CATEGORIES, GRAPHICS_EVENTS


REQUEST_ID = re.compile(r'[A-Za-z0-9_-]{1,80}')
VERSION = re.compile(r'[0-9][A-Za-z0-9.+~:_-]{0,127}')
UNAVAILABLE = 'indisponível'
SERVICE_STATES = {'active', 'inactive', 'failed', 'activating', 'deactivating', UNAVAILABLE}
CHECKS = {
    'system': {
        'versão': lambda value: matches(value, VERSION),
        'kernel': lambda value: matches(value, VERSION),
        'espaço livre no sistema (bytes)': lambda value: type(value) is int and 0 <= value < 2**63,
    },
    'network': {'conectividade': lambda value: enum(value, {
        'none', 'portal', 'limited', 'full', 'unknown', UNAVAILABLE})},
    'updates': {
        'reinício solicitado pelo sistema': lambda value: type(value) is bool,
        'destino de recuperação configurado': lambda value: type(value) is bool,
        'última proteção': lambda value: enum(value, {
            'created', 'failed', 'disabled', 'not-configured', UNAVAILABLE}),
        'revisão associada à proteção': lambda value: isinstance(value, str)
        and re.fullmatch(r'[A-Za-z0-9._-]{1,80}', value) is not None,
        'revisão preparada nesta conta': lambda value: isinstance(value, str)
        and re.fullmatch(r'[A-Za-z0-9._-]{1,80}', value) is not None,
        'código da última proteção': lambda value: type(value) is int and -255 <= value <= 255,
    },
    'graphics': {
        'sessão': lambda value: enum(value, {'wayland', 'x11', UNAVAILABLE}),
        **{name: lambda value: enum(value, SERVICE_STATES) for name in (
            'xdg-desktop-portal', 'plasma-xdg-desktop-portal-kde',
            'plasma-kwin_wayland', 'pipewire', 'wireplumber')},
        **{name: lambda value: value == UNAVAILABLE or type(value) is int and 0 <= value <= 30
           for name in GRAPHICS_EVENTS},
    },
}


def matches(value, pattern):
    return isinstance(value, str) and (value == UNAVAILABLE or pattern.fullmatch(value) is not None)


def enum(value, allowed):
    return isinstance(value, str) and value in allowed


def request_id(value):
    if not isinstance(value, str) or not REQUEST_ID.fullmatch(value):
        raise ValueError('Identificador de solicitação inválido.')
    return value


def checked_report(report):
    if (not isinstance(report, dict) or set(report) != {'schema', 'diagnóstico'}
            or type(report['schema']) is not int or report['schema'] != 1):
        raise ValueError('Formato de diagnóstico inválido.')
    sections = report['diagnóstico']
    fields = {label: CHECKS[key] for key, label in CATEGORIES.items()}
    if not isinstance(sections, dict) or not sections or not sections.keys() <= fields.keys():
        raise ValueError('Selecione categorias de diagnóstico conhecidas.')
    for label, values in sections.items():
        rules = fields[label]
        if (not isinstance(values, dict) or not values or not values.keys() <= rules.keys()
                or any(not rules[name](value) for name, value in values.items())):
            raise ValueError('O diagnóstico contém campos que não podem ser enviados.')
    return report


def dispatch(config, action, transport, source):
    if action == 'pending':
        response = transport(config, 'GET', '/v1/diagnostic')
        identifier = response['request_id']
        return {'request_id': None if identifier is None else request_id(identifier)}
    if action not in ('send', 'decline'):
        raise ValueError('Operação de suporte inválida.')
    raw = source.read(16 * 1024 + 1)
    if len(raw) > 16 * 1024:
        raise ValueError('Diagnóstico excede o limite de tamanho.')
    value = json.loads(raw)
    if action == 'decline':
        if not isinstance(value, dict) or set(value) != {'request_id'}:
            raise ValueError('Recusa de diagnóstico inválida.')
        transport(config, 'POST', '/v1/diagnostic', {'request_id': request_id(value['request_id']), 'decline': True})
        return {'declined': True}
    if not isinstance(value, dict) or set(value) != {'request_id', 'report'}:
        raise ValueError('Envio de diagnóstico inválido.')
    payload = {'request_id': request_id(value['request_id']), 'report': checked_report(value['report'])}
    transport(config, 'POST', '/v1/diagnostic', payload)
    return {'sent': True}


def main():
    from update_waves import read_config, request_json
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise ValueError('A operação de suporte requer autorização local.')
    config = read_config()
    if not config or not config.get('endpoint'):
        raise ValueError('Este computador não está cadastrado no serviço da organização.')
    return dispatch(config, sys.argv[1], request_json, sys.stdin.buffer)


if __name__ == '__main__':
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError):
        print('Não foi possível consultar ou enviar o diagnóstico à organização.', file=sys.stderr)
        sys.exit(1)
