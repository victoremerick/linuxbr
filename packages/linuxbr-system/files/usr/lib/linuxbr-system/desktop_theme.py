"""Use installed desktop icons, including sessions without a theme plugin."""
from pathlib import Path
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator


def initialize():
    app=QCoreApplication.instance()
    if app is not None and not hasattr(app,'_linuxbr_qt_translator'):
        translator=QTranslator(app)
        if translator.load(QLocale(),'qtbase','_',QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(translator)
        app._linuxbr_qt_translator=translator
    paths=QIcon.themeSearchPaths()
    for path in (str(Path.home()/'.local/share/icons'),'/usr/local/share/icons','/usr/share/icons'):
        if path not in paths and Path(path).is_dir():paths.append(path)
    QIcon.setThemeSearchPaths(paths)
    if not QIcon.themeName():QIcon.setThemeName('breeze')
    QIcon.setFallbackThemeName('breeze')
