"""
Экран для скачивания видео.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QProgressBar, QLabel, 
    QFileDialog, QFrame, QSpacerItem, QSizePolicy, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, QSize, QRect, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QFont, QPainter, QColor, QPen
import urllib.request
import time
import weakref
import os

from pathlib import Path
from typing import Optional, Dict, List

from vidify.core.downloader import (
    VideoDownloader, VideoInfoFetcher, DownloadStatus, is_valid_url, setup_paths, open_folder
)


# Выносим класс для отображения миниатюр за пределы метода, чтобы его можно было переиспользовать
class AspectRatioPixmapLabel(QLabel):
    """Виджет для отображения изображений с сохранением пропорций."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1, 1)
        self.setScaledContents(False)
        self.setAlignment(Qt.AlignCenter)
        self._pixmap = None

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        super().setPixmap(pixmap)
        self.updateGeometry()

    def heightForWidth(self, width):
        if self._pixmap and self._pixmap.width() > 0:
            return int(width * self._pixmap.height() / self._pixmap.width())
        return super().heightForWidth(width)

    def sizeHint(self):
        w = self.width()
        return QSize(w, self.heightForWidth(w))

    def paintEvent(self, event):
        if not self._pixmap:
            return super().paintEvent(event)
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Рассчитываем размер для отображения с сохранением пропорций
        pixmap_width = self._pixmap.width()
        pixmap_height = self._pixmap.height()
        
        # Проверяем, что pixmap имеет ненулевую ширину и высоту
        if pixmap_width <= 0 or pixmap_height <= 0:
            return super().paintEvent(event)
        
        # Получаем размеры виджета
        widget_width = self.width()
        widget_height = self.height()
        
        # Определяем, как масштабировать
        width_ratio = widget_width / pixmap_width
        height_ratio = widget_height / pixmap_height
        
        # Выбираем меньший коэффициент, чтобы изображение полностью помещалось
        scale_factor = min(width_ratio, height_ratio)
            
        # Рассчитываем новые размеры
        scaled_width = int(pixmap_width * scale_factor)
        scaled_height = int(pixmap_height * scale_factor)
        
        # Рассчитываем положение для центрирования
        x = (widget_width - scaled_width) // 2
        y = (widget_height - scaled_height) // 2
        
        # Отрисовываем изображение
        target_rect = QRect(x, y, scaled_width, scaled_height)
        painter.drawPixmap(target_rect, self._pixmap)
        painter.end()


# Выносим загрузку миниатюры в отдельный класс
class ThumbnailLoader(QThread):
    """Поток для асинхронной загрузки миниатюр."""
    
    thumbnail_ready = pyqtSignal(QPixmap)
    error = pyqtSignal()
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            # Устанавливаем короткий таймаут для быстрого ответа
            req = urllib.request.Request(
                self.url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            data = urllib.request.urlopen(req, timeout=3).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.thumbnail_ready.emit(pixmap)
        except Exception:
            self.error.emit()


class DownloadScreen(QWidget):
    """Экран скачивания видео."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("downloadTab")
        
        # Устанавливаем шрифт для всего экрана
        self.default_font = QFont("Monocraft", 24)
        self.setFont(self.default_font)
        
        # Инициализация переменных
        self.is_downloading = False
        self.input_path, self.output_path, self.temp_path = setup_paths()
        self.save_path = self.input_path
        self.download_thread: Optional[VideoDownloader] = None
        self.info_thread: Optional[VideoInfoFetcher] = None
        self.thumbnail_loader: Optional[ThumbnailLoader] = None
        self.video_info: Optional[Dict] = None
        self._last_fetched_url = ''
        self.progress_complete = False
        
        # Активные потоки для освобождения ресурсов
        self._active_threads: List[QThread] = []
        
        # Инициализация UI
        self._init_ui()
        
        # Таймер для отложенного поиска
        self.url_timer = QTimer()
        self.url_timer.setSingleShot(True)
        self.url_timer.timeout.connect(self.preview_video)
        
        # Добавляем оверлей с изображением поверх всех элементов
        self._add_overlay_image()

    def _init_ui(self) -> None:
        """Инициализирует интерфейс экрана."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)  # Уменьшаем отступы
        
        # Основной горизонтальный макет (левая и правая части)
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(20)  # Уменьшаем расстояние между колонками
        
        # Добавляем верхний отступ для всего контента
        self.layout.addSpacing(70)
        
        # Инициализация левой и правой частей
        self._init_left_panel()
        self._init_right_panel()
        
        # Добавляем основной макет в макет страницы
        self.layout.addLayout(self.content_layout)
    
    def _init_left_panel(self) -> None:
        """Инициализирует левую панель с миниатюрой."""
        # Левая часть - только миниатюра и информация
        self.left_layout = QVBoxLayout()
        self.left_layout.setContentsMargins(100, 0, 0, 0)  # Увеличиваем левый отступ на 40 пикселей
        self.left_layout.setSpacing(0)
        
        # Контейнер для миниатюры в соотношении 9:16
        self.thumbnail_container = QFrame()
        self.thumbnail_container.setObjectName("thumbnailContainer")
        self.thumbnail_container.setFont(self.default_font)
        self.thumbnail_container.setFrameShape(QFrame.NoFrame)  # Убираем рамку у контейнера
        self.thumbnail_container.setStyleSheet("border: none; background-color: transparent;")  # Убираем любые рамки через CSS
        
        # Уменьшаем размер контейнера для большей компактности
        thumbnail_width = 284  # Было 320
        thumbnail_height = int(thumbnail_width * 9 / 16)  # Меняем соотношение на 9:16
        
        self.thumbnail_container.setFixedSize(thumbnail_width, thumbnail_height)
        
        # Используем вертикальный layout для центрирования миниатюры
        thumbnail_container_layout = QVBoxLayout(self.thumbnail_container)
        thumbnail_container_layout.setContentsMargins(0, 0, 0, 0)
        thumbnail_container_layout.setAlignment(Qt.AlignCenter)
        
        # Миниатюра внутри контейнера
        self.thumbnail_label = AspectRatioPixmapLabel(self)
        self.thumbnail_label.setMinimumSize(260, 160)  # Уменьшаем минимальный размер
        self.thumbnail_label.setText("Введите URL видео")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("border: none; border-radius: 0px; background-color: #202020;")
        self.thumbnail_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        thumbnail_container_layout.addWidget(self.thumbnail_label)
        
        # Выравниваем по верхнему краю, а не по центру
        self.left_layout.addWidget(self.thumbnail_container, 0, Qt.AlignTop)
        
        # Добавляем отступ между превью и кнопкой конвертера
        self.left_layout.addSpacing(200)
        
        # Добавляем кнопку "Конвертер" под превью
        self.convert_button = QPushButton("Convert", self)
        self.convert_button.setObjectName("convertButton")
        self.convert_button.setMinimumHeight(36)
        self.convert_button.setFont(QFont("Monocraft", 16))  # Уменьшаем размер шрифта с 18 до 16
        self.convert_button.setFixedWidth(140)  # Уменьшаем ширину со 160 до 120
        self.convert_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.convert_button.clicked.connect(self.open_converter)
        
        # Создаем горизонтальный layout для размещения кнопки левее
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(80, 0, 0, 0)
        button_layout.addWidget(self.convert_button)
        button_layout.addStretch()  # Добавляем растягивающийся элемент справа от кнопки
        self.left_layout.addLayout(button_layout)
        
        # Добавляем отступ после кнопки конвертера
        self.left_layout.addSpacing(25)
        
        # Добавляем растягивающийся пробел для выравнивания (после миниатюры)
        self.left_layout.addStretch()
        
        # Создаем контейнер левой части для установки минимальной ширины
        left_container = QFrame()
        left_container.setLayout(self.left_layout)
        left_container.setMinimumWidth(300)  # Уменьшаем с 360
        left_container.setFont(self.default_font)
        
        # Устанавливаем соотношение для левого и правого макета (5:4)
        self.content_layout.addWidget(left_container, 4)
    
    def _init_right_panel(self) -> None:
        """Инициализирует правую панель с элементами управления."""
        # Правая часть - все элементы управления
        self.right_layout = QVBoxLayout()
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)  # Убираем автоматический отступ
        
        # Убираем верхний растягивающийся пробел, чтобы элементы начинались сверху
        # self.right_layout.addStretch()
        
        # URL ввод в отдельной строке на полную ширину
        self.url_input = QLineEdit(self)
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText("Вставьте ссылку на видеоϟϟ ")
        self.url_input.textChanged.connect(self.on_url_changed)
        self.url_input.setMinimumHeight(36)  # Уменьшаем высоту с 40
        self.url_input.setFont(QFont("Monocraft", 18))  # Уменьшаем размер шрифта
        self.url_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.right_layout.addWidget(self.url_input)
        
        # Одинаковый отступ после каждого элемента
        self.right_layout.addSpacing(25)
        
        # Кнопка выбора папки
        self.folder_button = QPushButton("Выбрать папку", self)
        self.folder_button.setObjectName("folderButton")
        self.folder_button.clicked.connect(self.choose_folder)
        self.folder_button.setMinimumHeight(36)  # Уменьшаем высоту с 40
        self.folder_button.setFont(QFont("Monocraft", 18))  # Уменьшаем размер шрифта
        self.folder_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.right_layout.addWidget(self.folder_button)
        
        # Одинаковый отступ
        self.right_layout.addSpacing(25)
        
        # Инициализация кнопок скачивания
        self._init_download_buttons()
        
        # Одинаковый отступ
        self.right_layout.addSpacing(25)

        # Кнопка открытия папки
        self.open_folder_button = QPushButton("Открыть папку", self)
        self.open_folder_button.setObjectName("openFolderButton")
        self.open_folder_button.clicked.connect(self.open_download_folder)
        self.open_folder_button.setMinimumHeight(36)  # Уменьшаем высоту с 40
        self.open_folder_button.setFont(QFont("Monocraft", 18))  # Уменьшаем размер шрифта
        self.open_folder_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.right_layout.addWidget(self.open_folder_button)

        # Одинаковый отступ
        self.right_layout.addSpacing(25)

        # Прогресс-бар и статус
        self._init_progress_section()
        
        # Растягивающийся пробел в конце для центрирования
        self.right_layout.addStretch()
        
        # Создаем контейнер правой части
        right_container = QFrame()
        right_container.setLayout(self.right_layout)
        right_container.setFont(self.default_font)
        
        # Устанавливаем соотношение для левого и правого макета (5:4)
        self.content_layout.addWidget(right_container, 5)
    
    def _init_download_buttons(self) -> None:
        """Инициализирует кнопки скачивания и отмены."""
        # Кнопки скачивания и отмены в одной строке
        download_buttons_layout = QHBoxLayout()
        download_buttons_layout.setContentsMargins(0, 0, 0, 0)
        download_buttons_layout.setSpacing(20)  # Уменьшаем расстояние между кнопками
        
        # Кнопка скачивания
        self.download_button = QPushButton("Скачать", self)
        self.download_button.setObjectName("downloadButton")
        self.download_button.clicked.connect(self.download_video)
        self.download_button.setEnabled(False)
        self.download_button.setMinimumHeight(36)  # Уменьшаем высоту с 40
        self.download_button.setFont(QFont("Monocraft", 18))  # Уменьшаем размер шрифта
        download_buttons_layout.addWidget(self.download_button, 2)
        
        # Кнопка отмены
        self.cancel_button = QPushButton("Отмена", self)
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.cancel_download)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setMinimumHeight(36)  # Уменьшаем высоту с 40
        self.cancel_button.setFont(QFont("Monocraft", 18))  # Уменьшаем размер шрифта
        download_buttons_layout.addWidget(self.cancel_button, 1)
        
        self.right_layout.addLayout(download_buttons_layout)
    
    def _init_progress_section(self) -> None:
        """Инициализирует прогресс-бар и метку статуса."""
        # Прогресс-бар
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("downloadProgressBar")
        self.progress_bar.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        self.progress_bar.setMinimumHeight(26)  # Уменьшаем высоту с 30
        self.progress_bar.setFont(QFont("Monocraft", 16))  # Уменьшаем размер шрифта
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.right_layout.addWidget(self.progress_bar)

        # Статус
        self.status_label = QLabel(DownloadStatus.READY.value, self)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setFont(QFont("Monocraft", 14))  # Уменьшаем размер шрифта
        self.right_layout.addWidget(self.status_label)
        
        # Одинаковый отступ после секции прогресса
        self.right_layout.addSpacing(25)

    def _set_status(self, status: DownloadStatus, **kwargs) -> None:
        """Устанавливает статус с учетом форматирования."""
        self.status_label.setText(status.value.format(**kwargs) if '{' in status.value else status.value)

    def _set_ui_state(self, downloading: bool) -> None:
        """Управляет состоянием UI-кнопок в зависимости от загрузки."""
        self.is_downloading = downloading
        self.download_button.setEnabled(not downloading and self.video_info is not None)
        self.folder_button.setEnabled(not downloading)
        self.cancel_button.setEnabled(downloading)
        self.url_input.setEnabled(not downloading)
        self.convert_button.setEnabled(not downloading)

    def choose_folder(self) -> None:
        """Выбирает папку для сохранения."""
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения", str(self.save_path))
        if folder and folder != str(self.save_path):
            self.save_path = Path(folder)
            self._set_status(DownloadStatus.FOLDER_CHOSEN, folder=folder)
    
    def on_url_changed(self) -> None:
        """Обрабатывает изменение URL и запускает предпросмотр с задержкой."""
        url = self.url_input.text().strip()
        
        # Сбрасываем состояние, если URL пуст
        if not url:
            self.reset_preview()
            return
        
        # Если URL не изменился и уже был загружен - не делаем ничего
        if url == self._last_fetched_url and self.video_info:
            return
        
        # Только если URL - YouTube или другой поддерживаемый сервис
        is_youtube = 'youtube.com' in url or 'youtu.be' in url
        if is_youtube or is_valid_url(url):
            # Запоминаем URL
            self._last_fetched_url = url
            
            # Отменяем предыдущий таймер и запускаем новый
            # Это позволяет не делать запрос при каждом нажатии клавиши
            self.url_timer.stop()
            self.url_timer.start(700)  # 700ms задержка
    
    def reset_preview(self) -> None:
        """Сбрасывает предпросмотр."""
        self.video_info = None
        self._last_fetched_url = ''
        self.thumbnail_label.setText("Введите URL видео")
        self.thumbnail_label.setPixmap(QPixmap())
        self.download_button.setEnabled(False)
        
        # Отменяем все активные потоки
        self._cancel_active_threads()
    
    def preview_video(self) -> None:
        """Получает предварительную информацию о видео."""
        url = self.url_input.text().strip()
        if not url:
            self.reset_preview()
            return
            
        if not is_valid_url(url):
            self.reset_preview()
            self._set_status(DownloadStatus.ERROR, error="Некорректный URL!")
            return
        
        # Если уже идет загрузка информации, отменяем ее
        if self.info_thread and self.info_thread.isRunning():
            self._cancel_thread(self.info_thread)
            
        # Показываем индикацию загрузки
        self.thumbnail_label.setText("Загрузка...")
        self.download_button.setEnabled(False)
        self._set_status(DownloadStatus.PREVIEW)
        
        # Создаем и запускаем поток получения информации
        self.info_thread = VideoInfoFetcher(url)
        self.info_thread.info_ready.connect(self.display_preview)
        self.info_thread.error.connect(self._on_preview_error)
        
        # Добавляем поток в список активных и запускаем
        self._add_active_thread(self.info_thread)
        self.info_thread.start(QThread.HighPriority)
    
    def display_preview(self, video_info: Dict) -> None:
        """Отображает предпросмотр видео."""
        self.video_info = video_info
        
        # Загружаем миниатюру, если она доступна
        thumbnail_url = video_info.get('thumbnail')
        if thumbnail_url:
            # Если есть предыдущий загрузчик миниатюр, отменяем его
            if self.thumbnail_loader and self.thumbnail_loader.isRunning():
                self._cancel_thread(self.thumbnail_loader)
                
            # Создаем и запускаем поток для загрузки миниатюры
            self.thumbnail_loader = ThumbnailLoader(thumbnail_url)
            
            # Создаем специальную функцию для обработки миниатюры
            def process_thumbnail(pixmap):
                self.thumbnail_label.setPixmap(pixmap)
                self.thumbnail_label.setText("")
            
            self.thumbnail_loader.thumbnail_ready.connect(process_thumbnail)
            self.thumbnail_loader.error.connect(
                lambda: self.thumbnail_label.setText("Миниатюра недоступна")
            )
            
            # Добавляем поток в список активных и запускаем
            self._add_active_thread(self.thumbnail_loader)
            self.thumbnail_loader.start(QThread.HighPriority)
        else:
            self.thumbnail_label.setText("Миниатюра недоступна")
        
        # Обновляем состояние UI
        self.download_button.setEnabled(True)
        self._set_status(DownloadStatus.READY)
    
    def _on_preview_error(self, error_msg: str) -> None:
        """Обработчик ошибок получения информации."""
        self.reset_preview()
        self.thumbnail_label.setText("Ошибка загрузки")
        self._set_status(DownloadStatus.ERROR, error=error_msg)

    def download_video(self) -> None:
        """Скачивает видео."""
        if self.is_downloading:
            self._set_status(DownloadStatus.ALREADY)
            return
            
        url = self.url_input.text().strip()
        if not url:
            self._set_status(DownloadStatus.NO_URL)
            return
            
        if not is_valid_url(url):
            self._set_status(DownloadStatus.ERROR, error="Некорректный URL!")
            return
            
        if not self.save_path.exists():
            self._set_status(DownloadStatus.ERROR, error="Папка для сохранения не существует!")
            return
            
        self._set_ui_state(True)
        self.progress_bar.setValue(0)
        self._set_status(DownloadStatus.PREPARE)
        
        # Если есть предыдущий поток загрузки, отменяем его
        if self.download_thread and self.download_thread.isRunning():
            self._cancel_thread(self.download_thread)
        
        # Создаем и запускаем поток скачивания
        self.download_thread = VideoDownloader(url, str(self.save_path))
        
        # Флаг для контроля обновлений прогресс-бара
        self.progress_complete = False
        
        # Оборачиваем функцию обновления прогресс-бара
        def update_progress(value):
            if not self.progress_complete:
                self.progress_bar.setValue(value)
                if value == 100:
                    self.progress_complete = True
        
        self.download_thread.update_progress.connect(update_progress)
        self.download_thread.update_status.connect(self.status_label.setText)
        self.download_thread.download_complete.connect(self.on_download_finished)
        self.download_thread.finished_with_error.connect(self._on_download_error)
        
        # Добавляем поток в список активных и запускаем
        self._add_active_thread(self.download_thread)
        self.download_thread.start()

    def cancel_download(self) -> None:
        """Отменяет скачивание."""
        if self.download_thread and self.is_downloading:
            self.download_thread.abort()
            self._set_ui_state(False)
            self._set_status(DownloadStatus.CANCELED)
            self.progress_bar.setValue(0)

    def on_download_finished(self) -> None:
        """Обработчик окончания скачивания."""
        self._set_ui_state(False)
        self._set_status(DownloadStatus.FINISHED)

    def _on_download_error(self, error_msg: str) -> None:
        """Обработчик ошибок скачивания."""
        self._set_ui_state(False)
        self.progress_bar.setValue(0)
        self._set_status(DownloadStatus.ERROR, error=error_msg)

    def open_download_folder(self) -> None:
        """Открывает папку скачивания."""
        try:
            open_folder(str(self.save_path))
        except Exception as e:
            self._set_status(DownloadStatus.ERROR, error=f"Ошибка открытия папки: {e}")
    
    def open_converter(self) -> None:
        """Открывает вкладку конвертера."""
        try:
            # Получаем доступ к родительскому TabWidget
            parent = self.parent()
            while parent and not isinstance(parent, QTabWidget):
                parent = parent.parent()
            
            # Если нашли TabWidget, переключаемся на вкладку "Конвертер"
            if parent:
                # Индекс вкладки "Конвертер" равен 2 (считаем с 0)
                parent.setCurrentIndex(2)
            else:
                self._set_status(DownloadStatus.ERROR, error="Не удалось переключиться на вкладку конвертера")
        except Exception as e:
            self._set_status(DownloadStatus.ERROR, error=f"Ошибка при переключении на конвертер: {str(e)}")
    
    def _add_active_thread(self, thread: QThread) -> None:
        """Добавляет поток в список активных потоков."""
        # Используем слабую ссылку для предотвращения утечки памяти
        self._active_threads.append(thread)
        
        # Автоматическое удаление из списка при завершении
        thread.finished.connect(lambda: self._remove_thread(thread))
    
    def _remove_thread(self, thread: QThread) -> None:
        """Удаляет поток из списка активных."""
        if thread in self._active_threads:
            self._active_threads.remove(thread)
    
    def _cancel_thread(self, thread: QThread) -> None:
        """Отменяет выполнение потока."""
        if hasattr(thread, 'abort'):
            thread.abort()
        
        # Ждем небольшое время для корректной отмены
        if thread.isRunning():
            thread.wait(300)  # Ожидаем до 300мс
    
    def _cancel_active_threads(self) -> None:
        """Отменяет все активные потоки."""
        for thread in self._active_threads[:]:  # Копируем список, так как он может изменяться
            self._cancel_thread(thread)
    
    def closeEvent(self, event) -> None:
        """Обработчик закрытия виджета."""
        # Отменяем все активные потоки перед закрытием
        self._cancel_active_threads()
        super().closeEvent(event)

    def _add_overlay_image(self) -> None:
        """Добавляет изображение-оверлей поверх всех элементов."""
        # Путь к изображению в ассетах
        image_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                 "assets", "Прямоугольник 12.png")
        
        # Создаем метку для изображения
        self.overlay_label = QLabel(self)
        self.overlay_label.setObjectName("overlayImage")
        
        # Загружаем изображение
        overlay_pixmap = QPixmap(image_path)
        if not overlay_pixmap.isNull():
            # Настройки скейлинга - измените эти параметры по вашему усмотрению
            self.overlay_scale = 0.35  # 1.0 = 100% оригинального размера, 0.5 = 50% и т.д.
            
            # Параметр для растяжения по горизонтали
            self.horizontal_stretch = 1.02  # 1.0 = без растяжения, >1.0 = растягивание
            
            # Настройки позиционирования - измените эти параметры по вашему усмотрению
            # x=0, y=0 - левый верхний угол
            # Отрицательные значения можно использовать для отсчета от правого/нижнего края
            self.overlay_x = -655  # -10 означает 10 пикселей от правого края
            self.overlay_y = 50   # 10 пикселей от верхнего края
            
            # Масштабируем изображение, если нужно
            if self.overlay_scale != 1.0 or self.horizontal_stretch != 1.0:
                # Рассчитываем новую ширину и высоту с учетом растяжения по горизонтали
                scaled_width = int(overlay_pixmap.width() * self.overlay_scale * self.horizontal_stretch)
                scaled_height = int(overlay_pixmap.height() * self.overlay_scale)
                
                # Используем IgnoreAspectRatio для независимого масштабирования ширины и высоты
                overlay_pixmap = overlay_pixmap.scaled(scaled_width, scaled_height, 
                                                      Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            
            # Устанавливаем изображение на метку
            self.overlay_label.setPixmap(overlay_pixmap)
            
            # Устанавливаем размер в соответствии с изображением
            self.overlay_label.setFixedSize(overlay_pixmap.size())
            
            # Размещаем поверх всех элементов
            self.overlay_label.raise_()
            
            # Устанавливаем прозрачный фон
            self.overlay_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            
            # Располагаем изображение в соответствии с заданными координатами
            self._position_overlay()
        
        # Подключаем обработчик изменения размера для репозиционирования оверлея
        self._original_resize_event = self.resizeEvent
        self.resizeEvent = self._on_resize
        
    def _position_overlay(self) -> None:
        """Позиционирует оверлей в соответствии с заданными координатами."""
        if not hasattr(self, 'overlay_label') or not self.overlay_label.pixmap():
            return
            
        pixmap_width = self.overlay_label.pixmap().width()
        pixmap_height = self.overlay_label.pixmap().height()
        
        # Вычисляем позицию с учетом отрицательных координат (отсчет от правого/нижнего края)
        x_pos = self.overlay_x if self.overlay_x >= 0 else self.width() + self.overlay_x - pixmap_width
        y_pos = self.overlay_y if self.overlay_y >= 0 else self.height() + self.overlay_y - pixmap_height
        
        # Устанавливаем позицию
        self.overlay_label.move(x_pos, y_pos)

    def _on_resize(self, event) -> None:
        """Обработчик изменения размера окна для репозиционирования оверлея."""
        # Вызываем оригинальный обработчик, если он был
        if hasattr(self, '_original_resize_event'):
            self._original_resize_event(event)
            
        # Репозиционируем оверлей при изменении размера окна
        self._position_overlay() 