"""
Главный класс приложения и оконный интерфейс.
"""
import os
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QMessageBox, QTabBar, QStylePainter, QStyleOptionTab, QStyle
from PyQt5.QtCore import Qt, QDir, QRect, QPoint, QSize
from PyQt5.QtGui import QFontDatabase, QFont

from vidify.ui.screens.download_screen import DownloadScreen
from vidify.ui.screens.video_edit_screen import VideoEditScreen
from vidify.ui.screens.video_convert_screen import VideoConvertScreen


# Кастомный TabBar для скрытия вкладок
class CustomTabBar(QTabBar):
    """Кастомный TabBar с возможностью скрытия вкладок."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hidden_tabs = []
    
    def setTabVisible(self, index, visible):
        """Установка видимости вкладки."""
        if not visible and index not in self.hidden_tabs:
            self.hidden_tabs.append(index)
        elif visible and index in self.hidden_tabs:
            self.hidden_tabs.remove(index)
        self.update()
    
    def isTabVisible(self, index):
        """Проверка видимости вкладки."""
        return index not in self.hidden_tabs
    
    def tabSizeHint(self, index):
        """Переопределяем размер вкладки для скрытых вкладок."""
        if index in self.hidden_tabs:
            return QSize(0, 0)
        return super().tabSizeHint(index)
    
    def paintEvent(self, event):
        """Переопределяем отрисовку, чтобы не рисовать скрытые вкладки."""
        painter = QStylePainter(self)
        style_option = QStyleOptionTab()
        
        for i in range(self.count()):
            if i in self.hidden_tabs:
                continue
            self.initStyleOption(style_option, i)
            painter.drawControl(QStyle.CE_TabBarTabShape, style_option)
            painter.drawControl(QStyle.CE_TabBarTabLabel, style_option)


# Кастомный TabWidget с возможностью скрытия вкладок
class CustomTabWidget(QTabWidget):
    """Кастомный TabWidget с возможностью скрытия вкладок."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(CustomTabBar(self))
    
    def setTabVisible(self, index, visible):
        """Установка видимости вкладки."""
        self.tabBar().setTabVisible(index, visible)
    
    def isTabVisible(self, index):
        """Проверка видимости вкладки."""
        return self.tabBar().isTabVisible(index)


class MainWindow(QMainWindow):
    """Главное окно приложения."""
    
    def __init__(self):
        super().__init__()
        
        # Загружаем пользовательский шрифт
        self.monocraft_loaded = self._load_fonts()
        
        # Подключаем стили
        style_path = Path(__file__).parent.parent / 'assets' / 'style.qss'
        if style_path.exists():
            with open(style_path, "r", encoding="utf-8") as f:
                self.base_stylesheet = f.read()
                
                # Если шрифт Monocraft не найден, заменяем его на системный моноширинный шрифт
                if not self.monocraft_loaded:
                    # Используем Consolas, Courier New или monospace - в зависимости от того, что есть в системе
                    fallback_font = self._get_fallback_font()
                    self.base_stylesheet = self.base_stylesheet.replace("'Monocraft'", f"'{fallback_font}'")
                
                self.setStyleSheet(self.base_stylesheet)
        else:
            print(f"Предупреждение: файл стилей не найден по пути {style_path}")
            self.base_stylesheet = ""

        # Настройка основного окна
        self._setup_window()
        
        # Создание вкладок
        self.tabs = CustomTabWidget(self)
        self.setCentralWidget(self.tabs)
        self._create_tabs()
        
        # Стили для разных вкладок
        self._setup_tab_styles()
        
        # Подключаем обработчик изменения вкладки
        self.tabs.currentChanged.connect(self._update_tab_style)
        
        # Инициализируем стиль для первой вкладки
        self._update_tab_style(0)
        
        # Показываем сообщение, если шрифт не найден
        if not self.monocraft_loaded:
            QMessageBox.information(
                self, 
                "Шрифт не найден", 
                "Шрифт Monocraft не найден. Приложение будет использовать системный шрифт.\n"
                "Пожалуйста, установите шрифт Monocraft и перезапустите приложение для лучшего отображения.\n"
                "Инструкции по установке находятся в папке assets/fonts"
            )

    def _get_fallback_font(self):
        """Возвращает моноширинный шрифт, доступный в системе."""
        # Список моноширинных шрифтов в порядке предпочтения
        monospace_fonts = ["Consolas", "Courier New", "DejaVu Sans Mono", "Liberation Mono", "monospace"]
        
        # Получаем список доступных шрифтов
        available_fonts = QFontDatabase().families()
        
        # Проверяем каждый шрифт из списка
        for font in monospace_fonts:
            for available_font in available_fonts:
                if font.lower() in available_font.lower():
                    return font
        
        # Если ничего не найдено, возвращаем "monospace"
        return "monospace"

    def _load_fonts(self):
        """Загружает пользовательские шрифты из ресурсов приложения."""
        fonts_dir = Path(__file__).parent.parent / 'assets' / 'fonts'
        if fonts_dir.exists():
            # Проверяем наличие файлов шрифтов Monocraft
            font_files = [
                fonts_dir / 'Monocraft.ttc',  # Новый формат (TrueType Collection)
                fonts_dir / 'Monocraft.ttf'   # Старый формат (для совместимости)
            ]
            
            for font_file in font_files:
                if font_file.exists() and font_file.stat().st_size > 0:
                    font_id = QFontDatabase.addApplicationFont(str(font_file))
                    if font_id != -1:
                        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
                        print(f"Шрифт {font_family} успешно загружен из {font_file.name}")
                        return True
            
            print(f"Подходящих файлов шрифта не найдено в {fonts_dir}")
            return False
        else:
            print(f"Директория шрифтов не найдена: {fonts_dir}")
            return False

    def _setup_window(self):
        """Настройка параметров окна."""
        # Центрирование окна
        screen = QApplication.desktop().screenGeometry()
        x = (screen.width() - 1200) // 2
        y = (screen.height() - 800) // 2
        self.setGeometry(x, y, 1200, 800)
        self.setWindowTitle("VIDIFY")
        self.setFixedSize(1200, 800)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)

    def _setup_tab_styles(self):
        """Настройка стилей для различных вкладок."""
        self.tab_styles = {
            0: "QTabWidget::pane { border-top: 10px groove #555555; background-color: #181818; padding:60px; }",  # Скачивание
            1: "QTabWidget::pane { border-top: 10px groove #555555; background-color: #181818; padding:30px 30px 0px 30px;}",  # Уникализация
            2: "QTabWidget::pane { border-top: 10px groove #555555; background-color: #181818; padding:30px 30px 0px 30px;}",  # Конвертация
            3: "QTabWidget::pane { border-top: 10px groove #555555; background-color: #181818; }",  # Загрузка
            4: "QTabWidget::pane { border-top: 10px groove #555555; background-color: #181818; }",  # Мониторинг
            5: "QTabWidget::pane { border-top: 10px groove #555555; background-color: #181818; }"   # Аккаунты
        }

    def _update_tab_style(self, index):
        """Обновляет стиль панели вкладок при переключении на новую вкладку."""
        if index in self.tab_styles:
            # Комбинируем базовый стиль с новым стилем для QTabWidget::pane
            combined_style = self.base_stylesheet
            # Удаляем существующий стиль для QTabWidget::pane
            lines = combined_style.split('\n')
            filtered_lines = []
            skip_block = False
            for line in lines:
                if 'QTabWidget::pane {' in line:
                    skip_block = True
                elif skip_block and '}' in line:
                    skip_block = False
                    continue

                if not skip_block:
                    filtered_lines.append(line)

            combined_style = '\n'.join(filtered_lines)
            # Добавляем новый стиль для активной вкладки
            combined_style += '\n' + self.tab_styles[index]
            self.setStyleSheet(combined_style)

    def _create_tabs(self):
        """Создание вкладок приложения."""
        # Создаем экраны для функциональных вкладок
        download_tab = DownloadScreen()
        video_edit_tab = VideoEditScreen()
        video_convert_tab = VideoConvertScreen()
        
        # Создаем заглушки для будущих вкладок
        upload_tab = self._create_stub_tab("uploadTab")
        monitoring_tab = self._create_stub_tab("monitoringTab")
        account_tab = self._create_stub_tab("accountTab")

        # Добавляем вкладки
        self.tabs.addTab(download_tab, "Скачивание")
        self.tabs.addTab(video_edit_tab, "Уникализация")
        self.tabs.addTab(video_convert_tab, "Конвертер")
        self.tabs.addTab(upload_tab, "Загрузка")
        self.tabs.addTab(monitoring_tab, "Мониторинг")
        self.tabs.addTab(account_tab, "Аккаунты")
        
        # Скрываем вкладку конвертера (индекс 2)
        self.tabs.setTabVisible(2, False)

    def _create_stub_tab(self, object_name):
        """Создает заглушку для вкладки, которая еще не реализована."""
        tab = QWidget()
        tab.setObjectName(object_name)
        layout = QVBoxLayout(tab)
        layout.addStretch()
        return tab


def run_app():
    """Запускает приложение."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 