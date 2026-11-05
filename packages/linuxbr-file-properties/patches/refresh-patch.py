#!/usr/bin/python3
"""Refresh the reviewed KIO 6.13 patch from an unmodified source directory."""
import difflib
from pathlib import Path
import sys


def replace(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Contexto KIO incompatível: ' + before[:120])
    return text.replace(before, after, 1)


def transform(name, text):
    if name == 'kpropertiesdialog.h':
        return replace(text, 'public Q_SLOTS:\n', 'public Q_SLOTS:\n    /** Applies pending changes while keeping this dialog open. */\n    void apply();\n\n')
    if name == 'kpropertiesdialog.cpp':
        text = replace(text, '#include <KJobWidgets>\n', '#include <KJobWidgets>\n#include <KJob>\n#include <KMessageBox>\n')
        text = replace(text, '#include <QRegularExpression>\n', '#include <QRegularExpression>\n#include <QPushButton>\n')
        text = replace(text, '    bool m_aborted = false;\n', '''    bool m_aborted = false;
    bool m_applyOnly = false;
    bool m_applying = false;
    QMetaObject::Connection m_fileApplyConnection;
    QMetaObject::Connection m_permissionsApplyConnection;
''')
        text = replace(text, '    void insertPages();\n', '''    void insertPages();

    void refreshItems(int index, std::function<void()> finished)
    {
        if (index >= m_items.size()) {
            finished();
            return;
        }
        auto *job = KIO::stat(m_items.at(index).url(), KIO::HideProgressInfo);
        KJobWidgets::setWindow(job, q);
        QObject::connect(job, &KJob::result, q, [this, job, index, finished]() {
            if (job->error()) {
                q->abortApplying();
                KMessageBox::error(q, QStringLiteral("Não foi possível atualizar as propriedades. As operações anteriores podem já ter terminado.\\n") + job->errorText());
                return;
            }
            m_items[index] = KFileItem(job->statResult(), m_items.at(index).url());
            refreshItems(index + 1, finished);
        });
    }
''')
        text = replace(text, '    q->setFaceType(KPageDialog::Tabbed);\n', '''    q->setFaceType(KPageDialog::Tabbed);
    q->setStandardButtons(QDialogButtonBox::Ok | QDialogButtonBox::Cancel | QDialogButtonBox::Apply);
    QObject::connect(q->button(QDialogButtonBox::Apply), &QPushButton::clicked, q, &KPropertiesDialog::apply);
''')
        text = replace(text, 'void KPropertiesDialog::accept()\n{\n    d->m_aborted = false;\n', '''void KPropertiesDialog::apply()
{
    if (d->m_applying) {
        return;
    }
    d->m_applyOnly = true;
    accept();
}

void KPropertiesDialog::accept()
{
    if (d->m_applying) {
        return;
    }
    const bool applyOnly = d->m_applyOnly;
    d->m_applyOnly = false;
    d->m_aborted = false;
    d->m_applying = true;
    QObject::disconnect(d->m_fileApplyConnection);
    QObject::disconnect(d->m_permissionsApplyConnection);
    if (auto *ok = button(QDialogButtonBox::Ok)) ok->setEnabled(false);
    if (auto *apply = button(QDialogButtonBox::Apply)) apply->setEnabled(false);
''')
        text = replace(text, '    auto acceptAndClose = [this]() {\n        Q_EMIT applied();\n', '''    auto completeApply = [this, applyOnly]() {
        d->m_applying = false;
        if (auto *ok = button(QDialogButtonBox::Ok)) ok->setEnabled(true);
        if (auto *apply = button(QDialogButtonBox::Apply)) apply->setEnabled(true);
        Q_EMIT applied();
        if (applyOnly) {
            return;
        }
''')
        text = replace(text, '    const bool isAnyDirty = std::any_of', '''    auto acceptAndClose = [this, applyOnly, completeApply]() {
        if (applyOnly) {
            d->refreshItems(0, completeApply);
        } else {
            completeApply();
        }
    };

    const bool isAnyDirty = std::any_of''')
        text = replace(text, '        connect(d->m_permissionsPropsPlugin, &KFilePermissionsPropsPlugin::changesApplied, this, [applyOtherChanges]() {', '        d->m_permissionsApplyConnection = connect(d->m_permissionsPropsPlugin, &KFilePermissionsPropsPlugin::changesApplied, this, [applyOtherChanges]() {')
        text = replace(text, '        connect(d->m_filePropsPlugin, &KFilePropsPlugin::changesApplied, this, [this, applyPermissionsChanges, applyOtherChanges]() {', '        d->m_fileApplyConnection = connect(d->m_filePropsPlugin, &KFilePropsPlugin::changesApplied, this, [this, applyPermissionsChanges, applyOtherChanges]() {')
        text = replace(text, '    if (m_items.count() != 1) {\n        return;\n    }\n\n    const KFileItem item = m_items.first();', '    const bool multiple = m_items.count() > 1;\n\n    const KFileItem item = m_items.first();')
        text = replace(text, '    const auto filter = [mimetype, scheme](const KPluginMetaData &metaData) {\n', '''    const auto filter = [mimetype, scheme, multiple](const KPluginMetaData &metaData) {
        if (multiple && !metaData.value(QStringLiteral("X-KDE-SupportsMultipleFiles"), false)) {
            return false;
        }
''')
        return replace(text, 'void KPropertiesDialog::abortApplying()\n{\n    d->m_aborted = true;\n}', '''void KPropertiesDialog::abortApplying()
{
    d->m_aborted = true;
    d->m_applying = false;
    QObject::disconnect(d->m_fileApplyConnection);
    QObject::disconnect(d->m_permissionsApplyConnection);
    if (auto *ok = button(QDialogButtonBox::Ok)) ok->setEnabled(true);
    if (auto *apply = button(QDialogButtonBox::Apply)) apply->setEnabled(true);
}''')
    if name == 'kpropertiesdialogbuiltin_p.cpp':
        text = replace(text, 'void KFilePropsPlugin::postApplyChanges()\n{\n', '''void KFilePropsPlugin::postApplyChanges()
{
    if (!d->m_ui->fileNameLineEdit->isHidden()) {
        d->oldName = d->m_ui->fileNameLineEdit->text();
        while (d->oldName.endsWith(QLatin1Char(' '))) d->oldName.chop(1);
    }
    d->m_bFromTemplate = false;
''')
        text = replace(text, '    const bool recursive = d->cbRecursive && d->cbRecursive->isChecked();\n\n    if (!recursive) {\n        if (owner == d->strOwner) {', '''    const bool recursive = d->cbRecursive && d->cbRecursive->isChecked();
    const KFileItemList currentItems = properties->items();
    QString currentOwner = currentItems.constFirst().user();
    QString currentGroup = currentItems.constFirst().group();
    for (const auto &item : currentItems) {
        if (item.user() != currentOwner) currentOwner.clear();
        if (item.group() != currentGroup) currentGroup.clear();
    }

    if (!recursive) {
        if (owner == currentOwner) {''')
        text = replace(text, '        if (group == d->strGroup) {\n', '        if (group == currentGroup) {\n')
        text = replace(text, '    if (owner.isEmpty() && group.isEmpty() && !recursive && !permissionChange && !ACLChange && !defaultACLChange) {\n        return;\n', '''    if (owner.isEmpty() && group.isEmpty() && !recursive && !permissionChange && !ACLChange && !defaultACLChange) {
        setDirty(false);
        Q_EMIT changesApplied();
        return;
''')
        text = replace(text, '    // KSycoca update needed?\n', '    d->m_origDesktopFile = path;\n    d->m_origCommandStr = d->command();\n\n    // KSycoca update needed?\n')
        return text
    raise ValueError(name)


def main():
    root, destination = Path(sys.argv[1]), Path(sys.argv[2])
    patch = ['From: Linux BR\nSubject: [PATCH] KPropertiesDialog: apply pending changes without closing\n\nReuse the asynchronous native apply sequence and refresh its editing baseline.\nPrevent concurrent application and discard callbacks from a failed attempt.\n\n']
    for name in ('kpropertiesdialog.h', 'kpropertiesdialog.cpp', 'kpropertiesdialogbuiltin_p.cpp'):
        relative = 'src/widgets/' + name
        original = (root / relative).read_text()
        revised = transform(name, original)
        patch.extend(difflib.unified_diff(original.splitlines(keepends=True), revised.splitlines(keepends=True), 'a/' + relative, 'b/' + relative))
    destination.write_text(''.join(patch))


if __name__ == '__main__':
    main()
