"""Selections that use the entries and installation queue of the Loja."""

COLLECTIONS = {
    'Estudo': ('applications-education', ('libreoffice', 'okular', 'kcalc', 'kate')),
    'Criação': ('applications-graphics', ('gimp', 'inkscape', 'krita', 'kdenlive', 'audacity', 'obs')),
    'Trabalho': ('applications-office', ('libreoffice', 'thunderbird', 'keepassxc', 'skanpage', 'ark')),
    'Jogos': ('applications-games', ('steam', 'supertux', 'discord')),
}

EQUIVALENTS = {
    'libreoffice': (
        ('microsoft office', 'office 365', 'word', 'excel', 'powerpoint'),
        'Trabalha com ODF e abre DOCX, XLSX e PPTX. Revise a aparência e as fórmulas dos seus documentos. Macros e complementos do Office precisam de verificação própria.',
    ),
    'gimp': (
        ('photoshop', 'adobe photoshop'),
        'O formato de trabalho do GIMP é XCF. Na importação de PSD, confira as camadas e os efeitos de que precisa.',
    ),
    'ark': (
        ('winrar', '7-zip', '7zip'),
        'Abra arquivos compactados pelo Explorador. Os formatos disponíveis para abrir e criar dependem dos componentes instalados.',
    ),
    'thunderbird': (
        ('outlook', 'microsoft outlook'),
        'Configure o e-mail da conta. Confirme com o provedor o suporte a agendas compartilhadas, diretório e autenticação corporativa.',
    ),
    'kolourpaint': (
        ('paint', 'microsoft paint', 'mspaint'),
        'Desenhe e edite imagens simples. Confira na ficha o formato desejado antes de usar um arquivo do seu fluxo atual.',
    ),
    'kate': (
        ('notepad++', 'bloco de notas', 'notepad'),
        'Edite arquivos de texto e código. Revise os atalhos e as extensões disponíveis antes de migrar a configuração.',
    ),
}


def entries_for(entries, name):
    _, identifiers = COLLECTIONS[name]
    return [item for item in entries if item['id'] in identifiers]


def with_equivalents(entries, query):
    from store_backend import folded

    value = ' '.join(folded(query).split())
    if not value:
        return entries
    resolved = []
    for item in entries:
        mapping = EQUIVALENTS.get(item['id'])
        if mapping and value in mapping[0]:
            names, differences = mapping
            item = dict(item, keywords=item.get('keywords', '') + ' ' + ' '.join(names),
                        note='Alternativa para ' + query + '. ' + differences)
        resolved.append(item)
    return resolved
