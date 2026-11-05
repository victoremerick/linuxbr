// SPDX-License-Identifier: GPL-3.0-or-later
#include <KFileItem>
#include <KPageWidget>
#include <KPageWidgetModel>
#include <KPluginFactory>
#include <KPropertiesDialog>
#include <KPropertiesDialogPlugin>

#include <QApplication>
#include <QCheckBox>
#include <QCloseEvent>
#include <QClipboard>
#include <QComboBox>
#include <QDesktopServices>
#include <QDateTime>
#include <QDialog>
#include <QDialogButtonBox>
#include <QFileInfo>
#include <QEvent>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QIcon>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPointer>
#include <QProcess>
#include <QProgressBar>
#include <QPushButton>
#include <QRegularExpression>
#include <QScrollArea>
#include <QStandardPaths>
#include <QTimer>
#include <QTreeWidget>
#include <QVBoxLayout>
#include <functional>
#include <memory>
#include <utility>

namespace {
QString helper()
{
    const QString overridePath = qEnvironmentVariable("LINUXBR_PROPERTIES_HELPER");
    return overridePath.isEmpty() ? QStringLiteral("/usr/lib/linuxbr-file-properties/backend.py") : overridePath;
}

QLabel *note(const QString &text, QWidget *parent = nullptr)
{
    auto *label = new QLabel(text, parent);
    label->setTextFormat(Qt::PlainText);
    label->setWordWrap(true);
    label->setTextInteractionFlags(Qt::TextSelectableByMouse | Qt::TextSelectableByKeyboard);
    return label;
}

QPushButton *action(const QString &label, const QString &icon, QBoxLayout *layout)
{
    auto *button = new QPushButton(QIcon::fromTheme(icon), label);
    button->setAutoDefault(false);
    layout->addWidget(button);
    return button;
}

QLineEdit *readonly(const QString &name, QWidget *parent = nullptr)
{
    auto *line = new QLineEdit(parent);
    line->setObjectName(name);
    line->setReadOnly(true);
    return line;
}

class SharingOperation final : public QDialog
{
public:
    SharingOperation(const QString &mode, const QString &path, const QStringList &extra)
    {
        setAttribute(Qt::WA_DeleteOnClose);
        setWindowTitle(QStringLiteral("Compartilhamento — resultado da operação"));
        setWindowIcon(QIcon::fromTheme(QStringLiteral("folder-publicshare")));
        resize(600, 260);
        auto *layout = new QVBoxLayout(this);
        layout->addWidget(note(QStringLiteral("Aguarde a autorização do sistema e o resultado. Esta operação continua independente da janela de propriedades.")));
        auto *output = new QPlainTextEdit;
        output->setReadOnly(true);
        output->setPlainText(QStringLiteral("Solicitação em andamento…"));
        layout->addWidget(output, 1);
        auto *buttons = new QDialogButtonBox(QDialogButtonBox::Close);
        buttons->setEnabled(false);
        layout->addWidget(buttons);
        connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
        auto *process = new QProcess(this);
        connect(process, &QProcess::finished, this, [this, process, output, buttons](int code, QProcess::ExitStatus) {
            m_running = false;
            const auto data = QJsonDocument::fromJson(process->readAllStandardOutput().trimmed()).object();
            output->setPlainText(data.isEmpty() ? QStringLiteral("Não foi possível confirmar o resultado (%1). Consulte o estado do serviço e do firewall.").arg(code)
                : data.value(QStringLiteral("error")).toString(data.value(QStringLiteral("text")).toString()));
            buttons->setEnabled(true);
        });
        connect(process, &QProcess::errorOccurred, this, [this, output, buttons](QProcess::ProcessError error) {
            if (error == QProcess::FailedToStart) {
                m_running = false;
                output->setPlainText(QStringLiteral("O componente de compartilhamento não está disponível."));
                buttons->setEnabled(true);
            }
        });
        QStringList arguments{helper(), mode, path};
        arguments.append(extra);
        process->start(QStringLiteral("/usr/bin/python3"), arguments);
    }

    void reject() override
    {
        if (!m_running) QDialog::reject();
    }

protected:
    void closeEvent(QCloseEvent *event) override
    {
        if (m_running) event->ignore(); else QDialog::closeEvent(event);
    }

private:
    bool m_running = true;
};
}

class FileProperties final : public KPropertiesDialogPlugin
{
    Q_OBJECT
public:
    explicit FileProperties(QObject *parent)
        : KPropertiesDialogPlugin(parent)
    {
        if (properties->items().isEmpty()) {
            return;
        }
        m_multiple = properties->items().size() > 1;
        if (m_multiple) {
            QTimer::singleShot(0, this, &FileProperties::integrate);
            return;
        }
        const auto item = properties->item();
        const auto local = item.mostLocalUrl();
        m_path = local.isLocalFile() ? local.toLocalFile() : QString();
        m_link = item.isLink();
        QTimer::singleShot(0, this, &FileProperties::integrate);
        connect(properties, &KPropertiesDialog::propertiesClosed, this, &FileProperties::stopQueries);
        connect(properties, &KPropertiesDialog::applied, this, [this]() {
            stopQueries();
            const auto local = properties->item().mostLocalUrl();
            m_path = local.isLocalFile() ? local.toLocalFile() : QString();
            properties->setWindowTitle(QStringLiteral("Propriedades de %1").arg(properties->item().name()));
            if (auto *field = properties->findChild<QLineEdit *>(QStringLiteral("linuxbr-real-path"))) field->setText(m_path.isEmpty() ? properties->item().url().toDisplayString() : m_path);
            if (auto *field = properties->findChild<QLineEdit *>(QStringLiteral("linuxbr-familiar-location"))) {
                field->clear();
                if (!m_path.isEmpty()) {
                    QPointer<QLineEdit> guarded(field);
                    query(QStringLiteral("inspect"), {}, [guarded](const QJsonObject &data) {
                        if (guarded) {
                            guarded->setText(data.value(QStringLiteral("familiar")).toString());
                            guarded->setCursorPosition(0);
                        }
                    });
                } else {
                    field->setText(QStringLiteral("Origem remota. Datas e permissões são fornecidas pelo servidor."));
                }
            }
            if (m_hash) {
                m_hash->clear();
                m_hashStatus->setText(QStringLiteral("Propriedades aplicadas. Calcule novamente para validar o estado atual."));
            }
        });
    }

    ~FileProperties() override
    {
        stopQueries();
    }

private:
    QString m_path;
    bool m_link = false;
    bool m_multiple = false;
    bool m_cancelled = false;
    QPointer<QProcess> m_hashProcess;
    QPointer<QProcess> m_versionsProcess;
    QList<QPointer<QProcess>> m_processes;
    QComboBox *m_algorithm = nullptr;
    QLineEdit *m_reference = nullptr;
    QLineEdit *m_hash = nullptr;
    QLabel *m_hashStatus = nullptr;
    QProgressBar *m_hashProgress = nullptr;
    QPushButton *m_hashStart = nullptr;
    QPushButton *m_hashCancel = nullptr;
    QComboBox *m_environments = nullptr;
    QPlainTextEdit *m_compatibilityOutput = nullptr;
    QTreeWidget *m_versions = nullptr;
    QLabel *m_versionsStatus = nullptr;
    QWidget *m_detailsWidget = nullptr;
    QLabel *m_declaredDetails = nullptr;
    QPointer<QCheckBox> m_recursive;
    bool m_recursionApproved = false;

    bool eventFilter(QObject *watched, QEvent *event) override
    {
        if (watched == m_recursive && event->type() == QEvent::EnabledChange && !m_recursionApproved && m_recursive->isEnabled()) {
            m_recursive->setEnabled(false);
        }
        return KPropertiesDialogPlugin::eventFilter(watched, event);
    }

    void stopQueries()
    {
        const auto processes = m_processes;
        for (const auto &process : processes) {
            if (process && process->state() != QProcess::NotRunning) {
                disconnect(process, nullptr, this, nullptr);
                process->kill();
                if (!process->waitForFinished(150)) {
                    process->setParent(qApp);
                    connect(process, &QProcess::finished, process, &QObject::deleteLater);
                }
            }
        }
        m_processes.clear();
    }

    QProcess *query(const QString &mode, const QStringList &extra,
                    std::function<void(const QJsonObject &)> finished,
                    std::function<void(const QJsonObject &)> progress = {})
    {
        auto *process = new QProcess(this);
        m_processes.append(process);
        auto buffer = std::make_shared<QByteArray>();
        auto result = std::make_shared<QJsonObject>();
        auto parse = [process, buffer, result, progress]() {
            buffer->append(process->readAllStandardOutput());
            qsizetype newline;
            while ((newline = buffer->indexOf('\n')) >= 0) {
                const auto data = buffer->left(newline);
                buffer->remove(0, newline + 1);
                const auto object = QJsonDocument::fromJson(data).object();
                if (object.value(QStringLiteral("progress")).toBool()) {
                    if (progress) {
                        progress(object);
                    }
                } else if (!object.isEmpty()) {
                    *result = object;
                }
            }
        };
        connect(process, &QProcess::readyReadStandardOutput, this, parse);
        connect(process, &QProcess::finished, this, [this, process, result, parse, finished](int code, QProcess::ExitStatus status) {
            parse();
            if (result->isEmpty()) {
                result->insert(QStringLiteral("error"), status == QProcess::CrashExit
                    ? QStringLiteral("Consulta interrompida.")
                    : QStringLiteral("Não foi possível concluir a consulta (%1).").arg(code));
            }
            finished(*result);
            m_processes.removeAll(process);
            process->deleteLater();
        });
        connect(process, &QProcess::errorOccurred, this, [this, process, finished](QProcess::ProcessError error) {
            if (error == QProcess::FailedToStart) {
                finished({{QStringLiteral("error"), QStringLiteral("O componente de consulta não está disponível.")}});
                m_processes.removeAll(process);
                process->deleteLater();
            }
        });
        QStringList arguments{helper(), mode, m_path};
        arguments.append(extra);
        process->start(QStringLiteral("/usr/bin/python3"), arguments);
        return process;
    }

    QList<KPageWidgetItem *> pages() const
    {
        QList<KPageWidgetItem *> result;
        auto *pageWidget = properties->findChild<KPageWidget *>();
        if (!pageWidget) {
            return result;
        }
        auto *model = qobject_cast<KPageWidgetModel *>(pageWidget->model());
        if (model) {
            for (int row = 0; row < model->rowCount(); ++row) {
                result.append(model->item(model->index(row, 0)));
            }
        }
        return result;
    }

    void integrate()
    {
        auto existing = pages();
        if (existing.isEmpty()) {
            return;
        }
        if (m_multiple) {
            for (auto *page : std::as_const(existing)) {
                const auto name = page->name().remove(QLatin1Char('&'));
                if (!name.contains(QStringLiteral("Permission"), Qt::CaseInsensitive) && !name.contains(QStringLiteral("Permiss"), Qt::CaseInsensitive)) continue;
                page->setName(QStringLiteral("Segurança"));
                page->setIcon(QIcon::fromTheme(QStringLiteral("security-high")));
                auto *widget = page->widget();
                for (auto *check : widget->findChildren<QCheckBox *>(QString(), Qt::FindDirectChildrenOnly)) {
                    m_recursive = check;
                    check->installEventFilter(this);
                    check->setChecked(false);
                    check->setEnabled(false);
                    check->setToolTip(QStringLiteral("Selecione uma única pasta e confira o alcance para aplicar permissões às subpastas."));
                }
                auto *explanation = note(QStringLiteral("Seleção múltipla: os valores mistos e a edição dos itens selecionados são preservados. Para alterar também subpastas, selecione uma única pasta e confira o alcance; a recursão fica desabilitada nesta seleção."));
                explanation->setObjectName(QStringLiteral("linuxbr-multiple-security"));
                if (widget->layout()) widget->layout()->addWidget(explanation);
            }
            return;
        }
        existing.first()->setIcon(QIcon::fromTheme(QStringLiteral("document-properties")));
        enrichGeneral(existing.first()->widget());
        bool validationFound = false;
        for (auto *page : std::as_const(existing)) {
            const auto name = page->name().remove(QLatin1Char('&'));
            if (page->widget()->objectName() == QStringLiteral("ChecksumsWidget")) {
                page->setName(QStringLiteral("Validação"));
                page->setIcon(QIcon::fromTheme(QStringLiteral("document-encrypted")));
                for (auto *child : page->widget()->findChildren<QWidget *>(QString(), Qt::FindDirectChildrenOnly)) {
                    child->hide();
                }
                validation(page->widget());
                validationFound = true;
            } else if (name.contains(QStringLiteral("Permission"), Qt::CaseInsensitive)
                       || name.contains(QStringLiteral("Permiss"), Qt::CaseInsensitive)) {
                page->setName(QStringLiteral("Segurança"));
                page->setIcon(QIcon::fromTheme(QStringLiteral("security-high")));
                enrichSecurity(page->widget());
            } else if (name == QStringLiteral("Details") || name == QStringLiteral("Detalhes")) {
                m_detailsWidget = page->widget();
                page->setIcon(QIcon::fromTheme(QStringLiteral("view-list-details")));
            } else if (page->widget()->findChild<QWidget *>(QStringLiteral("programEdit"))
                       || name == QStringLiteral("Application") || name == QStringLiteral("Aplicativo")
                       || name == QStringLiteral("URL")) {
                page->setName(QStringLiteral("Atalho"));
                page->setIcon(QIcon::fromTheme(QStringLiteral("emblem-symbolic-link")));
            } else if (name == QStringLiteral("Share") || name.contains(QStringLiteral("Compartilh"), Qt::CaseInsensitive)) {
                page->setName(QStringLiteral("Compartilhamento"));
                page->setIcon(QIcon::fromTheme(QStringLiteral("folder-publicshare")));
                enrichSharing(page->widget());
            }
        }
        if (!validationFound && !properties->item().isDir()) {
            auto *page = new QWidget;
            page->setLayout(new QVBoxLayout);
            properties->addPage(page, QStringLiteral("Validação"))->setIcon(QIcon::fromTheme(QStringLiteral("document-encrypted")));
            validation(page);
        }
        const auto suffix = QFileInfo(m_path).suffix().toLower();
        if (!m_path.isEmpty() && suffix == QStringLiteral("exe")) {
            if (!m_detailsWidget) {
                m_detailsWidget = new QWidget;
                m_detailsWidget->setLayout(new QVBoxLayout);
                properties->addPage(m_detailsWidget, QStringLiteral("Detalhes"))->setIcon(QIcon::fromTheme(QStringLiteral("view-list-details")));
            }
            m_declaredDetails = note(QStringLiteral("Consultando os dados declarados no recurso de versão…"));
            m_detailsWidget->layout()->addWidget(m_declaredDetails);
            m_detailsWidget->layout()->addWidget(note(QStringLiteral("Os dados de versão e fabricante são declarações do arquivo. Eles não verificam a identidade do fornecedor ou uma assinatura digital.")));
        }
        if (!m_path.isEmpty() && (suffix == QStringLiteral("exe") || suffix == QStringLiteral("msi"))) {
            compatibility();
        }
        if (!m_path.isEmpty()) {
            previousVersions();
        }
        if (properties->metaObject()->indexOfMethod("apply()") >= 0) {
            auto *box = properties->findChild<QDialogButtonBox *>();
            if (box && !box->button(QDialogButtonBox::Apply)) {
                auto *apply = box->addButton(QDialogButtonBox::Apply);
                apply->setText(QStringLiteral("Aplicar"));
                apply->setIcon(QIcon::fromTheme(QStringLiteral("dialog-ok-apply")));
                connect(apply, &QPushButton::clicked, properties, [this]() {
                    QMetaObject::invokeMethod(properties, "apply", Qt::DirectConnection);
                });
            }
        }
    }

    void enrichGeneral(QWidget *widget)
    {
        if (!widget->layout()) {
            return;
        }
        auto *supplement = new QWidget(widget);
        supplement->setObjectName(QStringLiteral("linuxbr-location"));
        auto *form = new QFormLayout(supplement);
        auto *path = readonly(QStringLiteral("linuxbr-real-path"));
        path->setText(m_path.isEmpty() ? properties->item().url().toDisplayString() : m_path);
        form->addRow(QStringLiteral("Caminho real:"), path);
        auto *familiar = readonly(QStringLiteral("linuxbr-familiar-location"));
        form->addRow(QStringLiteral("Localização:"), familiar);
        auto *extra = note(QString());
        form->addRow(extra);
        widget->layout()->addWidget(supplement);
        if (m_path.isEmpty()) {
            familiar->setText(QStringLiteral("Origem remota. Datas e permissões são fornecidas pelo servidor."));
            familiar->setCursorPosition(0);
            return;
        }
        query(QStringLiteral("inspect"), {}, [this, familiar, extra](const QJsonObject &data) {
            familiar->setText(data.value(QStringLiteral("familiar")).toString());
            familiar->setCursorPosition(0);
            QStringList text;
            if (data.contains(QStringLiteral("error"))) {
                text << data.value(QStringLiteral("error")).toString();
            }
            if (data.value(QStringLiteral("created")).isNull() && !QFileInfo(m_path).birthTime().isValid()) {
                text << QStringLiteral("Data de criação: indisponível quando não fornecida pelo sistema de arquivos.");
            }
            if (data.contains(QStringLiteral("shortcut"))) {
                text << data.value(QStringLiteral("shortcut")).toString();
            }
            extra->setText(text.join(QLatin1Char('\n')));
            if (m_declaredDetails) {
                QStringList details;
                const auto declared = data.value(QStringLiteral("declared")).toObject();
                for (auto field = declared.begin(); field != declared.end(); ++field) details << field.key() + QStringLiteral(": ") + field.value().toString();
                m_declaredDetails->setText(details.isEmpty() ? QStringLiteral("O arquivo não oferece dados de versão reconhecidos. Fabricante e versão: indisponíveis.") : details.join(QLatin1Char('\n')));
            }
        });
    }

    void enrichSecurity(QWidget *widget)
    {
        auto *box = qobject_cast<QBoxLayout *>(widget->layout());
        if (!box) {
            return;
        }
        auto *text = new QPlainTextEdit;
        text->setObjectName(QStringLiteral("linuxbr-effective-permissions"));
        text->setReadOnly(true);
        text->setMaximumHeight(130);
        text->setPlainText(m_path.isEmpty()
            ? QStringLiteral("Origem remota: o servidor decide quais permissões podem ser consultadas ou alteradas. Alterações dependem da sua autorização.")
            : QStringLiteral("Consulte o acesso efetivo e a máscara ACL. A consulta não modifica permissões."));
        box->addWidget(text);
        auto *row = new QHBoxLayout;
        box->addLayout(row);
        auto *read = action(QStringLiteral("Consultar acesso efetivo"), QStringLiteral("view-refresh"), row);
        read->setEnabled(!m_path.isEmpty());
        connect(read, &QPushButton::clicked, this, [this, text, read]() {
            read->setEnabled(false);
            query(QStringLiteral("security"), {}, [text, read](const QJsonObject &data) {
                read->setEnabled(true);
                text->setPlainText(data.value(QStringLiteral("error")).toString(data.value(QStringLiteral("text")).toString()));
            });
        });
        QCheckBox *recursive = nullptr;
        for (auto *check : widget->findChildren<QCheckBox *>(QString(), Qt::FindDirectChildrenOnly)) {
            recursive = check;
        }
        if (recursive) {
            const bool nativeAllowed = recursive->isEnabled();
            m_recursive = recursive;
            recursive->installEventFilter(this);
            recursive->setChecked(false);
            recursive->setEnabled(false);
            recursive->setToolTip(QStringLiteral("Calcule e confira o alcance antes de habilitar a aplicação às subpastas. Links e outras montagens não são incluídos."));
            auto *preview = action(QStringLiteral("Conferir alcance nas subpastas…"), QStringLiteral("view-list-tree"), row);
            preview->setEnabled(nativeAllowed && !m_path.isEmpty() && !m_link);
            connect(preview, &QPushButton::clicked, this, [this, recursive, text, preview]() {
                recursive->setChecked(false);
                m_recursionApproved = false;
                recursive->setEnabled(false);
                preview->setEnabled(false);
                text->setPlainText(QStringLiteral("Contando arquivos e pastas… Fechar a janela interrompe esta consulta."));
                query(QStringLiteral("preview"), {}, [this, recursive, text, preview](const QJsonObject &data) {
                    preview->setEnabled(true);
                    const auto message = data.contains(QStringLiteral("error"))
                        ? data.value(QStringLiteral("error")).toString()
                        : QStringLiteral("Alcance: %1 arquivos e %2 pastas. Links ignorados: %3. Outras montagens: %4. Falhas: %5.")
                            .arg(data.value(QStringLiteral("files")).toInt()).arg(data.value(QStringLiteral("folders")).toInt())
                            .arg(data.value(QStringLiteral("links")).toInt()).arg(data.value(QStringLiteral("mounts")).toInt())
                            .arg(data.value(QStringLiteral("errors")).toArray().size());
                    text->setPlainText(message);
                    if (!data.value(QStringLiteral("safe_recursive")).toBool()) {
                        text->appendPlainText(QStringLiteral("Aplicação recursiva desabilitada. Selecione separadamente pastas acessíveis no mesmo volume."));
                    } else if (QMessageBox::question(properties, QStringLiteral("Alcance das permissões"), message +
                               QStringLiteral("\nHabilitar a opção de aplicar às subpastas? A alteração só começa com OK ou Aplicar.")) == QMessageBox::Yes) {
                        m_recursionApproved = true;
                        recursive->setEnabled(true);
                    }
                }, [text](const QJsonObject &data) {
                    text->setPlainText(QStringLiteral("Contando: %1 arquivos; %2 pastas…")
                        .arg(data.value(QStringLiteral("files")).toInt()).arg(data.value(QStringLiteral("folders")).toInt()));
                });
            });
        }
    }

    void validation(QWidget *widget)
    {
        auto *body = new QWidget(widget);
        body->setObjectName(QStringLiteral("linuxbr-validation"));
        auto *layout = new QVBoxLayout(body);
        layout->addWidget(note(QStringLiteral("Calcule sob demanda e compare com a referência recebida. Hashes iguais confirmam igualdade com a referência; não comprovam ausência de malware ou identidade do fornecedor.")));
        auto *form = new QFormLayout;
        layout->addLayout(form);
        m_algorithm = new QComboBox;
        m_algorithm->setObjectName(QStringLiteral("linuxbr-hash-algorithm"));
        m_algorithm->addItem(QStringLiteral("SHA-256"), QStringLiteral("sha256"));
        m_algorithm->addItem(QStringLiteral("SHA-512"), QStringLiteral("sha512"));
        form->addRow(QStringLiteral("Algoritmo:"), m_algorithm);
        m_hash = readonly(QStringLiteral("linuxbr-hash"));
        form->addRow(QStringLiteral("Resultado:"), m_hash);
        m_reference = new QLineEdit;
        m_reference->setObjectName(QStringLiteral("linuxbr-hash-reference"));
        m_reference->setPlaceholderText(QStringLiteral("Cole somente os dígitos do hash de referência"));
        form->addRow(QStringLiteral("Referência:"), m_reference);
        auto *row = new QHBoxLayout;
        layout->addLayout(row);
        m_hashStart = action(QStringLiteral("Calcular"), QStringLiteral("view-refresh"), row);
        m_hashStart->setObjectName(QStringLiteral("linuxbr-hash-start"));
        m_hashCancel = action(QStringLiteral("Cancelar cálculo"), QStringLiteral("process-stop"), row);
        m_hashCancel->setObjectName(QStringLiteral("linuxbr-hash-cancel"));
        m_hashCancel->setEnabled(false);
        auto *copy = action(QStringLiteral("Copiar"), QStringLiteral("edit-copy"), row);
        m_hashProgress = new QProgressBar;
        m_hashProgress->setRange(0, 100);
        layout->addWidget(m_hashProgress);
        m_hashStatus = note(QStringLiteral("Pronto para calcular."));
        m_hashStatus->setObjectName(QStringLiteral("linuxbr-hash-status"));
        layout->addWidget(m_hashStatus);
        layout->addWidget(note(QStringLiteral("Assinatura: não verificada. Nenhum verificador e cadeia de confiança foram selecionados.")));
        layout->addStretch();
        if (auto *box = qobject_cast<QBoxLayout *>(widget->layout())) {
            box->insertWidget(0, body, 1);
        } else {
            widget->layout()->addWidget(body);
        }
        if (m_path.isEmpty() || m_link || !QFileInfo(m_path).isFile()) {
            m_hashStart->setEnabled(false);
            m_hashStatus->setText(m_link ? QStringLiteral("Link simbólico: abra as propriedades do arquivo de destino para validá-lo.")
                : QStringLiteral("Cálculo disponível para um arquivo regular local. Copie o arquivo remoto para um destino local e valide essa cópia."));
        }
        connect(m_hashStart, &QPushButton::clicked, this, &FileProperties::startHash);
        connect(m_hashCancel, &QPushButton::clicked, this, [this]() {
            m_cancelled = true;
            m_hashStatus->setText(QStringLiteral("Cancelamento solicitado. O resultado desta leitura será descartado."));
            if (m_hashProcess) {
                m_hashProcess->kill();
            }
        });
        connect(copy, &QPushButton::clicked, this, [this]() { QApplication::clipboard()->setText(m_hash->text()); });
        connect(m_reference, &QLineEdit::textChanged, this, &FileProperties::compareHash);
        connect(m_algorithm, &QComboBox::currentIndexChanged, this, [this]() {
            m_hash->clear();
            m_hashStatus->setText(QStringLiteral("Algoritmo alterado. Calcule novamente."));
        });
    }

    void startHash()
    {
        m_cancelled = false;
        m_hash->clear();
        m_hashProgress->setValue(0);
        m_hashStart->setEnabled(false);
        m_hashCancel->setEnabled(true);
        m_algorithm->setEnabled(false);
        m_hashStatus->setText(QStringLiteral("Lendo o arquivo…"));
        m_hashProcess = query(QStringLiteral("hash"), {QStringLiteral("--algorithm"), m_algorithm->currentData().toString()},
            [this](const QJsonObject &data) {
                m_hashProcess = nullptr;
                m_hashStart->setEnabled(true);
                m_hashCancel->setEnabled(false);
                m_algorithm->setEnabled(true);
                if (m_cancelled) {
                    m_hash->clear();
                    m_hashStatus->setText(QStringLiteral("Cálculo cancelado. Nenhum resultado foi mantido."));
                } else if (data.contains(QStringLiteral("error"))) {
                    m_hashStatus->setText(data.value(QStringLiteral("error")).toString());
                } else {
                    m_hash->setText(data.value(QStringLiteral("hash")).toString());
                    m_hashProgress->setValue(100);
                    compareHash();
                }
            }, [this](const QJsonObject &data) {
                if (m_cancelled) return;
                const double total = data.value(QStringLiteral("total")).toDouble();
                const double done = data.value(QStringLiteral("done")).toDouble();
                m_hashProgress->setValue(total > 0 ? qBound(0, int(done * 100 / total), 100) : 0);
                m_hashStatus->setText(QStringLiteral("Lidos %1 de %2 bytes.").arg(qint64(done)).arg(qint64(total)));
            });
    }

    void compareHash()
    {
        if (m_hash->text().isEmpty()) {
            return;
        }
        const QString reference = m_reference->text().trimmed().toLower();
        if (reference.isEmpty()) {
            m_hashStatus->setText(QStringLiteral("Cálculo concluído. Cole uma referência para comparar."));
        } else if (!QRegularExpression(QStringLiteral("^[0-9a-f]{%1}$").arg(m_hash->text().size())).match(reference).hasMatch()) {
            m_hashStatus->setText(QStringLiteral("Referência inválida: confira o algoritmo e a quantidade de dígitos hexadecimais."));
        } else {
            m_hashStatus->setText(reference == m_hash->text()
                ? QStringLiteral("Corresponde à referência informada.") : QStringLiteral("Não corresponde à referência informada."));
        }
    }

    void compatibility()
    {
        auto *page = new QWidget;
        page->setObjectName(QStringLiteral("linuxbr-compatibility"));
        auto *layout = new QVBoxLayout(page);
        layout->addWidget(note(QStringLiteral("Selecione explicitamente o ambiente deste programa. A configuração do Wine, incluindo versão do Windows, vídeo e escala, afeta todos os programas desse ambiente.")));
        auto *architecture = note(QStringLiteral("Consultando cabeçalho e ambientes…"));
        layout->addWidget(architecture);
        m_environments = new QComboBox;
        m_environments->setObjectName(QStringLiteral("linuxbr-environment"));
        layout->addWidget(m_environments);
        auto *row = new QHBoxLayout;
        layout->addLayout(row);
        auto *diagnose = action(QStringLiteral("Diagnóstico"), QStringLiteral("tools-report-bug"), row);
        auto *configure = action(QStringLiteral("Configurar Wine…"), QStringLiteral("configure"), row);
        auto *run = action(QStringLiteral("Abrir ou instalar…"), QStringLiteral("system-run"), row);
        auto *manager = new QPushButton(QIcon::fromTheme(QStringLiteral("applications-games")), QStringLiteral("Gerenciar ambientes e acompanhar operações…"));
        manager->setAutoDefault(false);
        layout->addWidget(manager);
        m_compatibilityOutput = new QPlainTextEdit;
        m_compatibilityOutput->setReadOnly(true);
        layout->addWidget(m_compatibilityOutput, 1);
        layout->addWidget(note(QStringLiteral("A consulta das propriedades não executa o arquivo. O ambiente de compatibilidade não isola programas maliciosos. As ações usam a sua conta normal.")));
        properties->addPage(page, QStringLiteral("Compatibilidade"))->setIcon(QIcon::fromTheme(QStringLiteral("applications-games")));
        diagnose->setEnabled(false);
        configure->setEnabled(false);
        run->setEnabled(false);
        query(QStringLiteral("compatibility"), {}, [this, architecture, diagnose, configure, run](const QJsonObject &data) {
            architecture->setText(data.contains(QStringLiteral("error")) ? data.value(QStringLiteral("error")).toString()
                : QStringLiteral("Arquitetura/formato declarado no cabeçalho: %1").arg(data.value(QStringLiteral("architecture")).toString()));
            m_environments->addItem(QStringLiteral("Selecione um ambiente…"), QString());
            for (const auto &value : data.value(QStringLiteral("environments")).toArray()) {
                const auto item = value.toObject();
                m_environments->addItem(item.value(QStringLiteral("name")).toString() + QStringLiteral(" — ") + item.value(QStringLiteral("architecture")).toString(), item.value(QStringLiteral("id")).toString());
            }
            m_compatibilityOutput->setPlainText(data.value(QStringLiteral("error")).toString());
            if (m_environments->count() == 1) {
                m_compatibilityOutput->appendPlainText(QStringLiteral("Nenhum ambiente disponível. Abra o gerenciador para criar ou selecionar um ambiente."));
            }
            const bool valid = data.value(QStringLiteral("error")).toString().isEmpty();
            const bool wine = data.value(QStringLiteral("wine")).toBool();
            connect(m_environments, &QComboBox::currentIndexChanged, this, [this, diagnose, configure, run, valid, wine]() {
                const bool selected = !m_environments->currentData().toString().isEmpty();
                diagnose->setEnabled(selected);
                configure->setEnabled(selected && wine);
                run->setEnabled(selected && valid && wine && !m_link);
            });
            if (!wine) {
                m_compatibilityOutput->appendPlainText(QStringLiteral("Wine não está instalado; execução e configuração indisponíveis."));
            }
        });
        auto perform = [this](const QString &mode) {
            query(mode, {QStringLiteral("--environment"), m_environments->currentData().toString()}, [this](const QJsonObject &data) {
                m_compatibilityOutput->setPlainText(data.value(QStringLiteral("error")).toString(data.value(QStringLiteral("text")).toString()));
            });
        };
        connect(diagnose, &QPushButton::clicked, this, [perform]() { perform(QStringLiteral("diagnose")); });
        connect(configure, &QPushButton::clicked, this, [this, perform]() {
            if (QMessageBox::question(properties, QStringLiteral("Configurar ambiente"),
                QStringLiteral("Abrir a configuração do ambiente selecionado? Os ajustes podem afetar os demais programas desse ambiente.")) == QMessageBox::Yes) {
                perform(QStringLiteral("configure"));
            }
        });
        connect(run, &QPushButton::clicked, this, [this, perform]() {
            if (QMessageBox::question(properties, QStringLiteral("Abrir programa Windows"),
                QStringLiteral("Executar ou instalar este arquivo no ambiente selecionado? Prossiga somente se confiar na origem. A operação tem seu próprio resultado e não é desfeita por Cancelar nesta janela.")) == QMessageBox::Yes) {
                perform(QStringLiteral("run"));
            }
        });
        connect(manager, &QPushButton::clicked, this, [this]() {
            QProcess::startDetached(QStringLiteral("/usr/bin/linuxbr-windows"), {m_path});
        });
    }

    void previousVersions()
    {
        auto *page = new QWidget;
        page->setObjectName(QStringLiteral("linuxbr-previous-versions"));
        auto *layout = new QVBoxLayout(page);
        layout->addWidget(note(QStringLiteral("As versões vêm das cópias pessoais configuradas no Kup. Pontos de restauração do sistema são gerenciados separadamente em Backup e recuperação.")));
        m_versions = new QTreeWidget;
        m_versions->setHeaderLabels({QStringLiteral("Data da cópia"), QStringLiteral("Plano")});
        m_versions->setRootIsDecorated(false);
        m_versions->header()->setSectionResizeMode(QHeaderView::ResizeToContents);
        layout->addWidget(m_versions, 1);
        auto *row = new QHBoxLayout;
        layout->addLayout(row);
        auto *refresh = action(QStringLiteral("Consultar versões"), QStringLiteral("view-refresh"), row);
        auto *cancel = action(QStringLiteral("Cancelar consulta"), QStringLiteral("process-stop"), row);
        cancel->setEnabled(false);
        auto *open = action(QStringLiteral("Abrir no explorador de versões…"), QStringLiteral("document-open"), row);
        open->setEnabled(false);
        auto *setup = new QPushButton(QIcon::fromTheme(QStringLiteral("preferences-system-backup")), QStringLiteral("Configurar cópias pessoais…"));
        setup->setAutoDefault(false);
        layout->addWidget(setup);
        m_versionsStatus = note(QStringLiteral("Consulte os destinos conectados para procurar este item. A consulta não monta discos nem cria cópias."));
        layout->addWidget(m_versionsStatus);
        layout->addWidget(note(QStringLiteral("O explorador nativo permite abrir versões e escolher o destino da restauração. Prefira outra pasta para conferir os arquivos antes de substituir os atuais. Uma restauração concluída não é desfeita por Cancelar nesta janela.")));
        properties->addPage(page, QStringLiteral("Versões anteriores"))->setIcon(QIcon::fromTheme(QStringLiteral("document-revert")));
        connect(refresh, &QPushButton::clicked, this, [this, refresh, cancel]() {
            refresh->setEnabled(false);
            cancel->setEnabled(true);
            m_versions->clear();
            m_versionsStatus->setText(QStringLiteral("Procurando versões nos planos desta conta…"));
            m_versionsProcess = query(QStringLiteral("versions"), {}, [this, refresh, cancel](const QJsonObject &data) {
                m_versionsProcess = nullptr;
                refresh->setEnabled(true);
                cancel->setEnabled(false);
                for (const auto &value : data.value(QStringLiteral("rows")).toArray()) {
                    const auto row = value.toObject();
                    auto *item = new QTreeWidgetItem(m_versions, {row.value(QStringLiteral("date")).toString(), row.value(QStringLiteral("plan")).toString()});
                    item->setData(0, Qt::UserRole, row.value(QStringLiteral("repository")).toString());
                }
                QStringList notes;
                if (data.contains(QStringLiteral("error"))) {
                    notes << data.value(QStringLiteral("error")).toString();
                }
                for (const auto &value : data.value(QStringLiteral("notes")).toArray()) {
                    notes << value.toString();
                }
                if (m_versions->topLevelItemCount()) {
                    notes.prepend(QStringLiteral("%1 versões contêm este caminho. O explorador nativo abre o item e permite escolher a data.").arg(m_versions->topLevelItemCount()));
                }
                m_versionsStatus->setText(notes.join(QLatin1Char('\n')));
            }, [this](const QJsonObject &data) {
                m_versionsStatus->setText(QStringLiteral("Versões localizadas até agora: %1.").arg(data.value(QStringLiteral("found")).toInt()));
            });
        });
        connect(cancel, &QPushButton::clicked, this, [this]() { if (m_versionsProcess) m_versionsProcess->kill(); });
        connect(m_versions, &QTreeWidget::itemSelectionChanged, this, [this, open]() { open->setEnabled(m_versions->currentItem() != nullptr); });
        connect(open, &QPushButton::clicked, this, [this]() {
            const auto item = m_versions->currentItem();
            if (item && !QProcess::startDetached(QStringLiteral("kup-filedigger"), {QStringLiteral("--path"), m_path, item->data(0, Qt::UserRole).toString()})) {
                QMessageBox::warning(properties, QStringLiteral("Versões anteriores"), QStringLiteral("Não foi possível abrir o explorador de versões do Kup."));
            }
        });
        connect(setup, &QPushButton::clicked, this, []() { QProcess::startDetached(QStringLiteral("kcmshell6"), {QStringLiteral("kcm_kup")}); });
    }

    void enrichSharing(QWidget *widget)
    {
        auto *outer = qobject_cast<QBoxLayout *>(widget->layout());
        if (!outer || m_path.isEmpty()) {
            return;
        }
        auto *content = new QWidget;
        auto *box = new QVBoxLayout(content);
        box->setContentsMargins(0, 0, 0, 0);
        while (outer->count()) {
            auto *item = outer->takeAt(0);
            if (auto *native = item->widget()) {
                native->setParent(content);
                native->setMinimumHeight(qMax(native->minimumHeight(), 380));
            }
            box->addItem(item);
        }
        auto *scroll = new QScrollArea(widget);
        scroll->setObjectName(QStringLiteral("linuxbr-sharing-scroll"));
        scroll->setFrameShape(QFrame::NoFrame);
        scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
        scroll->setWidgetResizable(true);
        scroll->setWidget(content);
        outer->addWidget(scroll);
        box->addWidget(note(QStringLiteral("A publicação e as permissões de rede são configuradas acima. O acesso convidado exige escolha explícita. Interromper a publicação mantém os arquivos.")));
        auto *text = new QPlainTextEdit;
        text->setObjectName(QStringLiteral("linuxbr-sharing-status"));
        text->setReadOnly(true);
        text->setMaximumHeight(100);
        box->addWidget(text);
        auto address = std::make_shared<QString>();
        auto *row = new QHBoxLayout;
        box->addLayout(row);
        auto *refresh = action(QStringLiteral("Consultar serviço e endereços"), QStringLiteral("view-refresh"), row);
        auto *copy = action(QStringLiteral("Copiar endereços"), QStringLiteral("edit-copy"), row);
        auto *open = action(QStringLiteral("Verificar acesso…"), QStringLiteral("network-connect"), row);
        copy->setEnabled(false);
        open->setEnabled(false);
        auto *network = new QHBoxLayout;
        box->addLayout(network);
        auto *service = action(QStringLiteral("Iniciar serviço SMB…"), QStringLiteral("media-playback-start"), network);
        auto *zones = new QComboBox;
        zones->setAccessibleName(QStringLiteral("Zona de rede para compartilhamento"));
        zones->addItem(QStringLiteral("Consulte as zonas da rede…"), QString());
        network->addWidget(zones);
        auto *firewall = action(QStringLiteral("Permitir SMB nesta rede…"), QStringLiteral("security-medium"), network);
        firewall->setEnabled(false);
        box->addWidget(note(QStringLiteral("Ativar o serviço ou liberar o firewall afeta o compartilhamento deste computador. Cada ação pede sua confirmação e, quando necessário, autorização do sistema. As permissões da pasta continuam sendo definidas no editor acima.")));
        service->setEnabled(!QStandardPaths::findExecutable(QStringLiteral("systemctl")).isEmpty());
        connect(refresh, &QPushButton::clicked, this, [this, refresh, text, copy, open, address, zones, firewall]() {
            refresh->setEnabled(false);
            query(QStringLiteral("sharing"), {QStringLiteral("--authorize-firewall")}, [refresh, text, copy, open, address, zones, firewall](const QJsonObject &data) {
                refresh->setEnabled(true);
                zones->clear();
                zones->addItem(QStringLiteral("Selecione a zona da rede…"), QString());
                for (const auto &value : data.value(QStringLiteral("zones")).toArray()) zones->addItem(value.toString(), value.toString());
                firewall->setEnabled(zones->count() > 1);
                QStringList lines;
                *address = QString();
                for (const auto &value : data.value(QStringLiteral("states")).toArray()) lines << value.toString();
                for (const auto &value : data.value(QStringLiteral("shares")).toArray()) {
                    const auto share = value.toObject();
                    lines << share.value(QStringLiteral("unc")).toString() << share.value(QStringLiteral("smb")).toString();
                    lines << QStringLiteral("Acesso de rede: %1; convidado: %2.").arg(share.value(QStringLiteral("acl")).toString(), share.value(QStringLiteral("guest")).toString());
                    if (address->isEmpty()) *address = share.value(QStringLiteral("smb")).toString();
                }
                if (address->isEmpty()) lines << (data.value(QStringLiteral("shares_complete")).toBool()
                    ? QStringLiteral("Nenhuma publicação desta pasta foi encontrada. Salve os ajustes e consulte novamente.")
                    : QStringLiteral("Não foi possível confirmar a publicação desta pasta. Os demais dados disponíveis foram preservados."));
                if (data.contains(QStringLiteral("error"))) lines << data.value(QStringLiteral("error")).toString();
                text->setPlainText(lines.join(QLatin1Char('\n')));
                copy->setEnabled(!address->isEmpty());
                open->setEnabled(!address->isEmpty());
            });
        });
        connect(copy, &QPushButton::clicked, this, [text]() { QApplication::clipboard()->setText(text->toPlainText()); });
        connect(open, &QPushButton::clicked, this, [address]() { QDesktopServices::openUrl(QUrl(*address)); });
        connect(service, &QPushButton::clicked, this, [this]() {
            QMessageBox confirm(QMessageBox::Question, QStringLiteral("Ativar compartilhamento SMB"),
                QStringLiteral("Iniciar o serviço Samba deste computador? As pastas já publicadas também ficarão disponíveis conforme suas permissões. Cancelar a janela de propriedades não desfaz esta ação."),
                QMessageBox::Yes | QMessageBox::Cancel, properties);
            confirm.setDefaultButton(QMessageBox::Cancel);
            auto *persist = new QCheckBox(QStringLiteral("Ativar o serviço também após reiniciar"));
            confirm.setCheckBox(persist);
            if (confirm.exec() != QMessageBox::Yes) return;
            (new SharingOperation(QStringLiteral("sharing-service"), m_path,
                persist->isChecked() ? QStringList{QStringLiteral("--persist")} : QStringList{}))->show();
        });
        connect(firewall, &QPushButton::clicked, this, [this, text, firewall, zones]() {
            const QString zone = zones->currentData().toString();
            if (zone.isEmpty()) {
                QMessageBox::information(properties, QStringLiteral("Rede do compartilhamento"), QStringLiteral("Selecione explicitamente uma zona de rede ativa."));
                return;
            }
            QMessageBox confirm(QMessageBox::Question, QStringLiteral("Permitir SMB na rede"),
                QStringLiteral("Permitir o serviço Samba na zona %1? A liberação vale para as interfaces dessa zona e para as pastas publicadas neste computador. Faça isso somente em uma rede apropriada. Cancelar a janela de propriedades não desfaz esta ação.").arg(zone),
                QMessageBox::Yes | QMessageBox::Cancel, properties);
            confirm.setDefaultButton(QMessageBox::Cancel);
            auto *persist = new QCheckBox(QStringLiteral("Manter esta liberação após reiniciar"));
            confirm.setCheckBox(persist);
            if (confirm.exec() != QMessageBox::Yes) return;
            QStringList extra{QStringLiteral("--zone"), zone};
            if (persist->isChecked()) extra << QStringLiteral("--persist");
            (new SharingOperation(QStringLiteral("sharing-firewall"), m_path, extra))->show();
        });
    }
};

K_PLUGIN_CLASS_WITH_JSON(FileProperties, "linuxbrfileproperties.json")
#include "properties.moc"
