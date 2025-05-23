"""
Экран для редактирования и уникализации видео.
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QSizePolicy,
    QProgressBar, QFrame, QLineEdit, QSlider, QStyle
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QIntValidator

from vidify.core.video_processor import (
    FFmpegProcessor, create_ffmpeg_command, check_ffmpeg_available, cleanup_temp_files
)
from vidify.ui.components.widgets import AspectFrameLabel, Switch


class VideoEditScreen(QWidget):
    """Экран для уникализации видео."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("videoEditTab")
        
        # Установка временных путей
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.temp_dir = os.path.join(app_dir, 'temp')
        self.output_dir = os.path.join(app_dir, 'output')
        self.input_dir = os.path.dirname(os.path.abspath(__file__))  # Инициализируем input_dir
        
        # Создаем временные директории, если их нет
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Очистка старых временных файлов
        cleanup_temp_files(self.temp_dir)
        
        # Текущий обрабатываемый файл
        self.input_path = ''
        self._preview_worker = None
        self._ffmpeg_video_worker = None
        
        # Параметры эффектов
        self.frame_enabled = False   # Рамка включена/выключена
        self.crop_top_value = 100    # Значение обрезки сверху в пикселях
        self.crop_bottom_value = 100  # Значение обрезки снизу в пикселях
        self.crop_sync = True        # Одинаковая обрезка сверху и снизу
        self.background_blur_value = 10   # Значение размытия фона в пикселях
        self.background_darkness_value = 50  # Затемнение фона в процентах (от 0 до 100)
        self.background_scale_value = 120   # Значение масштаба фона в процентах (от 100 до 200)
        self.background_video_path = ''     # Путь к видео для фона рамки
        self.watermark_video_path = ''      # Путь к видео-водяного знака
        self.flip_enabled = False   # Отражение включено/выключено
        self.brightness_enabled = False  # Затемнение включено/выключено
        self.brightness_value = 0   # Значение яркости от 0 до 100 (0: нормальная, 100: 25% затемнения)
        self.frame_time = "00:00:00.2"  # Время кадра для превью (по умолчанию 0.2 секунды)
        
        # Информация о видео
        self.video_width = 0       # Ширина видео
        self.video_height = 0       # Высота видео
        self.max_crop_per_side = 0  # Максимальное значение обрезки с одной стороны (49% от высоты)
        
        # Переменные состояния
        self.output_path = ''
        self.is_preview_generating = False
        
        # Таймер для дебаунсинга
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._delayed_preview_update)
        
        # Отслеживание состояния перетаскивания
        self.slider_being_dragged = False
        
        # Инициализация интерфейса
        self._init_ui()
        
        # Проверяем наличие FFmpeg
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Проверка наличия FFmpeg в системе"""
        if not check_ffmpeg_available():
            self.show_error('FFmpeg не найден в системе. Пожалуйста, установите FFmpeg для работы с приложением.')
            self.setEnabled(False)

    def _init_ui(self):
        """Инициализация интерфейса редактора видео."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы по краям
        main_layout.setSpacing(15)  # Оставляем расстояние между панелями
        
        # Левая колонка — настройки эффекта рамки
        left_panel = QFrame()
        left_panel.setObjectName('leftPanel')
        left_panel.setFrameShape(QFrame.NoFrame)  # Убираем рамку
        left_layout = QVBoxLayout(left_panel)
        
        # Стили для контейнеров-подложек
        group_style = """
            QFrame {
                background-color: #202020;
                border-radius: 8px;
                padding: 10px;
            }
        """
        
        # Стили для слайдеров
        slider_style = """
            QSlider::groove:horizontal {
                border: 1px solid #444444;
                height: 8px;
                background: #202020;
                margin: 2px 0;
                border-radius: 4px;
            }

            QSlider::handle:horizontal {
                background: #555555;
                border: 1px solid #444444;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            
            QSlider::sub-page:horizontal {
                background: #444444;
                border: 1px solid #444444;
                height: 8px;
                border-radius: 4px;
            }
        """
        
        # Стили для полей ввода
        input_style = """
            QLineEdit {
                background-color: #202020;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 3px;
            }
            
            QLineEdit:focus {
                border: 1px solid #555555;
            }
        """
        
        # Стили для выпадающих списков
        combo_style = """
            QComboBox {
                background-color: #202020;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 3px 10px 3px 10px;
            }
            
            QComboBox:focus {
                border: 1px solid #555555;
            }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left-width: 1px;
                border-left-color: #404040;
                border-left-style: solid;
            }
            
            QComboBox QAbstractItemView {
                background-color: #202020;
                border: 1px solid #404040;
                selection-background-color: #555555;
                color: #ffffff;
            }
        """
        
        # === ГРУППА: ЭФФЕКТ РАМКИ ===
        frame_group = QFrame()
        frame_group.setStyleSheet(group_style)
        frame_group_layout = QVBoxLayout(frame_group)
        frame_group_layout.setContentsMargins(10, 10, 10, 10)
        frame_group_layout.setSpacing(8)
        
        # Заголовок группы с переключателем
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        frame_group_title = QLabel("Рамка")
        frame_group_title.setStyleSheet("")
        header_layout.addWidget(frame_group_title)
        
        header_layout.addStretch(1)  # Добавляем растягивающийся элемент, чтобы переключатель был справа
        
        self.frame_switch = Switch()
        self.frame_switch.toggled.connect(self._on_frame_toggled)
        header_layout.addWidget(self.frame_switch)
        
        frame_group_layout.addWidget(header_widget)
        
        # Виджет для слайдера и значения
        crop_widget = QWidget()
        crop_layout = QVBoxLayout(crop_widget)
        crop_layout.setContentsMargins(0, 0, 0, 0)
        crop_layout.setSpacing(10)  # Отступ между элементами
        
        # === Верхняя граница обрезки ===
        crop_top_header = QWidget()
        crop_top_header_layout = QHBoxLayout(crop_top_header)
        crop_top_header_layout.setContentsMargins(0, 0, 0, 0)
        
        crop_top_label = QLabel("Верхняя граница:")
        crop_top_header_layout.addWidget(crop_top_label)
        
        crop_layout.addWidget(crop_top_header)
        
        # Ползунок верхней границы рамки
        crop_top_slider_widget = QWidget()
        crop_top_slider_layout = QHBoxLayout(crop_top_slider_widget)
        crop_top_slider_layout.setContentsMargins(0, 0, 0, 0)
        crop_top_slider_layout.setSpacing(10)
        
        # Добавляем отступ перед слайдером
        crop_top_slider_layout.addSpacing(10)
        
        self.crop_top_slider = QSlider(Qt.Horizontal)
        self.crop_top_slider.setMinimum(0)
        self.crop_top_slider.setMaximum(500)  # Временный максимум, будет обновлен после загрузки видео
        self.crop_top_slider.setValue(100)  # Начальное значение 100px
        self.crop_top_slider.setTickPosition(QSlider.TicksBelow)
        self.crop_top_slider.setTickInterval(100)
        self.crop_top_slider.setMinimumWidth(200)  # Минимальная ширина слайдера
        self.crop_top_slider.setStyleSheet(slider_style)
        self.crop_top_slider.valueChanged.connect(self._on_crop_top_slider_changed)
        # Добавляем обработчики нажатия и отпускания мыши для слайдера
        self.crop_top_slider.sliderPressed.connect(self._on_slider_pressed)
        self.crop_top_slider.sliderReleased.connect(self._on_slider_released)
        # Включаем перемещение слайдера при клике
        self.crop_top_slider.setPageStep(50)  # Шаг при клике на дорожку слайдера
        self.crop_top_slider.mousePressEvent = lambda event: self._slider_mouse_press_event(self.crop_top_slider, event)
        crop_top_slider_layout.addWidget(self.crop_top_slider, 1)  # Stretch=1
        
        # Поле ввода для значения верхней обрезки
        self.crop_top_input = QLineEdit("100")
        self.crop_top_input.setValidator(QIntValidator(0, 500))  # Временный максимум
        self.crop_top_input.setFixedWidth(60)
        self.crop_top_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.crop_top_input.setStyleSheet(input_style)
        self.crop_top_input.textChanged.connect(self._on_crop_top_input_changed)
        crop_top_slider_layout.addWidget(self.crop_top_input)
        
        crop_layout.addWidget(crop_top_slider_widget)
        
        # === Нижняя граница обрезки ===
        crop_bottom_header = QWidget()
        crop_bottom_header_layout = QHBoxLayout(crop_bottom_header)
        crop_bottom_header_layout.setContentsMargins(0, 0, 0, 0)
        
        crop_bottom_label = QLabel("Нижняя граница:")
        crop_bottom_header_layout.addWidget(crop_bottom_label)
        
        crop_layout.addWidget(crop_bottom_header)
        
        # Ползунок нижней границы рамки
        crop_bottom_slider_widget = QWidget()
        crop_bottom_slider_layout = QHBoxLayout(crop_bottom_slider_widget)
        crop_bottom_slider_layout.setContentsMargins(0, 0, 0, 0)
        crop_bottom_slider_layout.setSpacing(10)
        
        # Добавляем отступ перед слайдером
        crop_bottom_slider_layout.addSpacing(10)
        
        self.crop_bottom_slider = QSlider(Qt.Horizontal)
        self.crop_bottom_slider.setMinimum(0)
        self.crop_bottom_slider.setMaximum(500)  # Временный максимум, будет обновлен после загрузки видео
        self.crop_bottom_slider.setValue(100)  # Начальное значение 100px
        self.crop_bottom_slider.setTickPosition(QSlider.TicksBelow)
        self.crop_bottom_slider.setTickInterval(100)
        self.crop_bottom_slider.setMinimumWidth(200)  # Минимальная ширина слайдера
        self.crop_bottom_slider.setStyleSheet(slider_style)
        self.crop_bottom_slider.valueChanged.connect(self._on_crop_bottom_slider_changed)
        # Добавляем обработчики нажатия и отпускания мыши для слайдера
        self.crop_bottom_slider.sliderPressed.connect(self._on_slider_pressed)
        self.crop_bottom_slider.sliderReleased.connect(self._on_slider_released)
        # Включаем перемещение слайдера при клике
        self.crop_bottom_slider.setPageStep(50)  # Шаг при клике на дорожку слайдера
        self.crop_bottom_slider.mousePressEvent = lambda event: self._slider_mouse_press_event(self.crop_bottom_slider, event)
        crop_bottom_slider_layout.addWidget(self.crop_bottom_slider, 1)  # Stretch=1
        
        # Поле ввода для значения нижней обрезки
        self.crop_bottom_input = QLineEdit("100")
        self.crop_bottom_input.setValidator(QIntValidator(0, 500))  # Временный максимум
        self.crop_bottom_input.setFixedWidth(60)
        self.crop_bottom_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.crop_bottom_input.setStyleSheet(input_style)
        self.crop_bottom_input.textChanged.connect(self._on_crop_bottom_input_changed)
        crop_bottom_slider_layout.addWidget(self.crop_bottom_input)
        
        crop_layout.addWidget(crop_bottom_slider_widget)
        
        # Чекбокс синхронизации
        crop_sync_widget = QWidget()
        crop_sync_layout = QHBoxLayout(crop_sync_widget)
        crop_sync_layout.setContentsMargins(0, 0, 0, 0)
        
        from PyQt5.QtWidgets import QCheckBox
        self.crop_sync_checkbox = QCheckBox("Синхронизировать границы")
        self.crop_sync_checkbox.setChecked(self.crop_sync)
        self.crop_sync_checkbox.stateChanged.connect(self._on_crop_sync_changed)
        crop_sync_layout.addWidget(self.crop_sync_checkbox)
        
        crop_layout.addWidget(crop_sync_widget)
        
        frame_group_layout.addWidget(crop_widget)
        
        # Добавляем слайдер затемнения фона для рамки
        # Заголовок
        bg_darkness_label = QLabel("Затемнение фона:")
        bg_darkness_label.setStyleSheet("")
        frame_group_layout.addWidget(bg_darkness_label)
        
        # Виджет для слайдера затемнения фона
        bg_darkness_widget = QWidget()
        bg_darkness_layout = QHBoxLayout(bg_darkness_widget)
        bg_darkness_layout.setContentsMargins(0, 0, 0, 0)
        bg_darkness_layout.setSpacing(10)
        
        # Добавляем отступ перед слайдером
        bg_darkness_layout.addSpacing(10)
        
        # Ползунок настройки затемнения фона
        self.bg_darkness_slider = QSlider(Qt.Horizontal)
        self.bg_darkness_slider.setMinimum(0)
        self.bg_darkness_slider.setMaximum(100)
        self.bg_darkness_slider.setValue(0)  # Начальное значение 0%
        self.bg_darkness_slider.setTickPosition(QSlider.TicksBelow)
        self.bg_darkness_slider.setTickInterval(20)
        self.bg_darkness_slider.setMinimumWidth(200)
        self.bg_darkness_slider.setStyleSheet(slider_style)
        self.bg_darkness_slider.valueChanged.connect(self._on_bg_darkness_changed)
        # Добавляем обработчики нажатия и отпускания мыши для слайдера
        self.bg_darkness_slider.sliderPressed.connect(self._on_slider_pressed)
        self.bg_darkness_slider.sliderReleased.connect(self._on_slider_released)
        # Включаем перемещение слайдера при клике
        self.bg_darkness_slider.setPageStep(10)
        self.bg_darkness_slider.mousePressEvent = lambda event: self._slider_mouse_press_event(self.bg_darkness_slider, event)
        bg_darkness_layout.addWidget(self.bg_darkness_slider, 1)
        
        # Поле ввода для значения затемнения фона
        self.bg_darkness_input = QLineEdit("0")
        self.bg_darkness_input.setValidator(QIntValidator(0, 100))
        self.bg_darkness_input.setFixedWidth(60)
        self.bg_darkness_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.bg_darkness_input.setStyleSheet(input_style)
        self.bg_darkness_input.textChanged.connect(self._on_bg_darkness_input_changed)
        bg_darkness_layout.addWidget(self.bg_darkness_input)
        
        frame_group_layout.addWidget(bg_darkness_widget)
        
        # Добавляем слайдер размытия фона для рамки
        # Заголовок
        bg_blur_label = QLabel("Размытие фона:")
        bg_blur_label.setStyleSheet("")
        frame_group_layout.addWidget(bg_blur_label)
        
        # Виджет для слайдера размытия фона
        bg_blur_widget = QWidget()
        bg_blur_layout = QHBoxLayout(bg_blur_widget)
        bg_blur_layout.setContentsMargins(0, 0, 0, 0)
        bg_blur_layout.setSpacing(10)
        
        # Добавляем отступ перед слайдером
        bg_blur_layout.addSpacing(10)
        
        # Ползунок настройки размытия фона
        self.bg_blur_slider = QSlider(Qt.Horizontal)
        self.bg_blur_slider.setMinimum(0)  # Изменяем минимум на 0
        self.bg_blur_slider.setMaximum(100)
        self.bg_blur_slider.setValue(0)  # Начальное значение 0%
        self.bg_blur_slider.setTickPosition(QSlider.TicksBelow)
        self.bg_blur_slider.setTickInterval(10)
        self.bg_blur_slider.setMinimumWidth(200)
        self.bg_blur_slider.setStyleSheet(slider_style)
        self.bg_blur_slider.valueChanged.connect(self._on_bg_blur_changed)
        # Добавляем обработчики нажатия и отпускания мыши для слайдера
        self.bg_blur_slider.sliderPressed.connect(self._on_slider_pressed)
        self.bg_blur_slider.sliderReleased.connect(self._on_slider_released)
        # Включаем перемещение слайдера при клике
        self.bg_blur_slider.setPageStep(10)
        self.bg_blur_slider.mousePressEvent = lambda event: self._slider_mouse_press_event(self.bg_blur_slider, event)
        bg_blur_layout.addWidget(self.bg_blur_slider, 1)
        
        # Поле ввода для значения размытия фона
        self.bg_blur_input = QLineEdit("0")
        self.bg_blur_input.setValidator(QIntValidator(0, 100))
        self.bg_blur_input.setFixedWidth(60)
        self.bg_blur_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.bg_blur_input.setStyleSheet(input_style)
        self.bg_blur_input.textChanged.connect(self._on_bg_blur_input_changed)
        bg_blur_layout.addWidget(self.bg_blur_input)
        
        frame_group_layout.addWidget(bg_blur_widget)
        
        # Добавляем слайдер масштабирования фона для рамки
        # Заголовок
        bg_scale_label = QLabel("Масштаб фона:")
        bg_scale_label.setStyleSheet("")
        frame_group_layout.addWidget(bg_scale_label)
        
        # Виджет для слайдера масштабирования фона
        bg_scale_widget = QWidget()
        bg_scale_layout = QHBoxLayout(bg_scale_widget)
        bg_scale_layout.setContentsMargins(0, 0, 0, 0)
        bg_scale_layout.setSpacing(10)
        
        # Добавляем отступ перед слайдером
        bg_scale_layout.addSpacing(10)
        
        # Ползунок настройки масштабирования фона
        self.bg_scale_slider = QSlider(Qt.Horizontal)
        self.bg_scale_slider.setMinimum(100)  # Минимум 100% (оригинальный размер)
        self.bg_scale_slider.setMaximum(200)  # Максимум 200% (увеличение в 2 раза)
        self.bg_scale_slider.setValue(120)    # Начальное значение 120%
        self.bg_scale_slider.setTickPosition(QSlider.TicksBelow)
        self.bg_scale_slider.setTickInterval(20)
        self.bg_scale_slider.setMinimumWidth(200)
        self.bg_scale_slider.setStyleSheet(slider_style)
        self.bg_scale_slider.valueChanged.connect(self._on_bg_scale_changed)
        # Добавляем обработчики нажатия и отпускания мыши для слайдера
        self.bg_scale_slider.sliderPressed.connect(self._on_slider_pressed)
        self.bg_scale_slider.sliderReleased.connect(self._on_slider_released)
        # Включаем перемещение слайдера при клике
        self.bg_scale_slider.setPageStep(10)
        self.bg_scale_slider.mousePressEvent = lambda event: self._slider_mouse_press_event(self.bg_scale_slider, event)
        bg_scale_layout.addWidget(self.bg_scale_slider, 1)
        
        # Поле ввода для значения масштабирования фона
        self.bg_scale_input = QLineEdit("120")
        self.bg_scale_input.setValidator(QIntValidator(100, 200))
        self.bg_scale_input.setFixedWidth(60)
        self.bg_scale_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.bg_scale_input.setStyleSheet(input_style)
        self.bg_scale_input.textChanged.connect(self._on_bg_scale_input_changed)
        bg_scale_layout.addWidget(self.bg_scale_input)
        
        frame_group_layout.addWidget(bg_scale_widget)
        
        # Добавляем группу эффекта рамки в основной макет
        left_layout.addWidget(frame_group)
        
        left_layout.addStretch(1)
        main_layout.addWidget(left_panel, 1)

        # Центральная колонка — превью-кадр и кнопки
        center_panel = QFrame()
        center_panel.setObjectName('centerPanel')
        center_panel.setFrameShape(QFrame.NoFrame)  # Убираем рамку
        center_layout = QVBoxLayout(center_panel)
        
        # Виджет превью
        self.preview_container = QWidget()
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(20, 20, 20, 20)  # Добавляем отступы по 20px сверху и снизу
        
        # Добавляем кнопку для выбора другого кадра превью в правом верхнем углу
        preview_header = QWidget()
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(0, 0, 0, 5)
        
        preview_header_layout.addStretch(1)  # Пустое пространство слева
        
        self.next_frame_btn = QPushButton()
        self.next_frame_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSeekForward))
        self.next_frame_btn.setFixedSize(24, 24)
        self.next_frame_btn.setToolTip("Выбрать другой кадр для превью")
        self.next_frame_btn.setStyleSheet("""
            QPushButton {
                background-color: #303030;
                border: 1px solid #505050;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #404040;
            }
            QPushButton:pressed {
                background-color: #505050;
            }
        """)
        self.next_frame_btn.clicked.connect(self._next_preview_frame)
        preview_header_layout.addWidget(self.next_frame_btn)
        
        preview_layout.addWidget(preview_header)
        
        self.preview_label = AspectFrameLabel('')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(320)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setStyleSheet('QLabel {border: 2px solid #555555; border-radius: 8px; background: #151515;}')
        preview_layout.addWidget(self.preview_label)
        
        center_layout.addWidget(self.preview_container, stretch=4)
        
        # Кнопки действий
        btn_layout = QHBoxLayout()
        self.file_btn = QPushButton('Выбрать видео')
        self.file_btn.clicked.connect(self.choose_file)
        
        self.unique_btn = QPushButton('Уникализировать')
        self.unique_btn.clicked.connect(self.process_unique_video)
        self.unique_btn.setEnabled(False)
        
        # Кнопка отмены обработки
        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.clicked.connect(self._cancel_processing)
        self.cancel_btn.setVisible(False)
        
        btn_layout.addWidget(self.file_btn)
        btn_layout.addWidget(self.unique_btn)
        btn_layout.addWidget(self.cancel_btn)
        center_layout.addLayout(btn_layout)
        
        # Статус обработки
        self.status = QLabel('Готово')
        self.status.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.status)
        
        # Прогресс-бар
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setVisible(False)
        center_layout.addWidget(self.progress)
        
        main_layout.addWidget(center_panel, 3)
        
        # Правая колонка - дополнительные эффекты
        right_panel = QFrame()
        right_panel.setObjectName('rightPanel')
        right_panel.setFrameShape(QFrame.NoFrame)  # Убираем рамку
        right_layout = QVBoxLayout(right_panel)
        
        # === ГРУППА: ЭФФЕКТ ЗАТЕМНЕНИЯ ===
        brightness_group = QFrame()
        brightness_group.setStyleSheet(group_style)
        brightness_group_layout = QVBoxLayout(brightness_group)
        brightness_group_layout.setContentsMargins(10, 10, 10, 10)
        brightness_group_layout.setSpacing(8)
        
        # Заголовок группы с переключателем
        brightness_header_widget = QWidget()
        brightness_header_layout = QHBoxLayout(brightness_header_widget)
        brightness_header_layout.setContentsMargins(0, 0, 0, 0)
        
        brightness_group_title = QLabel("Затемнение")
        brightness_group_title.setStyleSheet("")
        brightness_header_layout.addWidget(brightness_group_title)
        
        brightness_header_layout.addStretch(1)  # Добавляем растягивающийся элемент, чтобы переключатель был справа
        
        self.brightness_switch = Switch()
        self.brightness_switch.toggled.connect(self._on_brightness_toggled)
        brightness_header_layout.addWidget(self.brightness_switch)
        
        brightness_group_layout.addWidget(brightness_header_widget)
        
        # Добавляем отступ после заголовка
        brightness_group_layout.addSpacing(5)
        
        # Виджет для слайдера и значения
        brightness_widget = QWidget()
        brightness_layout = QHBoxLayout(brightness_widget)
        brightness_layout.setContentsMargins(0, 0, 0, 0)
        brightness_layout.setSpacing(10)  # Увеличиваем расстояние между элементами
        
        # Добавляем отступ перед слайдером
        brightness_layout.addSpacing(10)
        
        # Ползунок яркости
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.setTickPosition(QSlider.TicksBelow)
        self.brightness_slider.setTickInterval(20)
        self.brightness_slider.setMinimumWidth(200)  # Устанавливаем минимальную ширину слайдера
        self.brightness_slider.setStyleSheet(slider_style)
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        # Добавляем обработчики нажатия и отпускания мыши для слайдера
        self.brightness_slider.sliderPressed.connect(self._on_slider_pressed)
        self.brightness_slider.sliderReleased.connect(self._on_slider_released)
        # Включаем перемещение слайдера при клике
        self.brightness_slider.setPageStep(10)  # Шаг при клике на дорожку слайдера
        self.brightness_slider.mousePressEvent = lambda event: self._slider_mouse_press_event(self.brightness_slider, event)
        brightness_layout.addWidget(self.brightness_slider, 1)  # Добавляем stretch-фактор 1
        
        # Поле ввода для значения яркости
        self.brightness_input = QLineEdit("0")
        self.brightness_input.setValidator(QIntValidator(0, 100))
        self.brightness_input.setFixedWidth(60)  # Увеличиваем ширину поля ввода
        self.brightness_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.brightness_input.setStyleSheet(input_style)
        self.brightness_input.textChanged.connect(self._on_brightness_input_changed)
        brightness_layout.addWidget(self.brightness_input)
        
        brightness_group_layout.addWidget(brightness_widget)
        
        # Добавляем группу эффекта затемнения в основной макет
        right_layout.addWidget(brightness_group)
        
        # Добавляем отступ между группами
        right_layout.addSpacing(15)
        
        # === ГРУППА: ЭФФЕКТ ОТЗЕРКАЛИВАНИЯ ===
        flip_group = QFrame()
        flip_group.setStyleSheet(group_style)
        flip_group_layout = QVBoxLayout(flip_group)
        flip_group_layout.setContentsMargins(10, 10, 10, 10)
        flip_group_layout.setSpacing(8)
        
        # Заголовок группы с переключателем
        flip_header_widget = QWidget()
        flip_header_layout = QHBoxLayout(flip_header_widget)
        flip_header_layout.setContentsMargins(0, 0, 0, 0)
        
        flip_group_title = QLabel("Отзеркаливание")
        flip_group_title.setStyleSheet("")
        flip_header_layout.addWidget(flip_group_title)
        
        flip_header_layout.addStretch(1)  # Добавляем растягивающийся элемент, чтобы переключатель был справа
        
        self.flip_switch = Switch()
        self.flip_switch.toggled.connect(self._on_flip_toggled)
        flip_header_layout.addWidget(self.flip_switch)
        
        flip_group_layout.addWidget(flip_header_widget)
        
        # Добавляем группу эффекта отзеркаливания в основной макет
        right_layout.addWidget(flip_group)
        
        # Добавляем отступ между группами
        right_layout.addSpacing(15)
        
        # === ГРУППА: ВИДЕО ФОН И WATERMARK ===
        videos_group = QFrame()
        videos_group.setStyleSheet(group_style)
        videos_group_layout = QVBoxLayout(videos_group)
        videos_group_layout.setContentsMargins(10, 10, 10, 10)
        videos_group_layout.setSpacing(8)
        
        # Заголовок группы
        videos_header = QLabel("Видео фон и watermark")
        videos_header.setStyleSheet("")
        videos_group_layout.addWidget(videos_header)
        
        # Добавляем отступ после заголовка
        videos_group_layout.addSpacing(5)
        
        # === ВЫБОР ВИДЕО ФОНА ===
        bg_video_widget = QWidget()
        bg_video_layout = QHBoxLayout(bg_video_widget)
        bg_video_layout.setContentsMargins(0, 0, 0, 0)
        bg_video_layout.setSpacing(10)
        
        # Заголовок
        bg_video_label = QLabel("Видео фон:")
        bg_video_layout.addWidget(bg_video_label)
        
        bg_video_layout.addStretch(1)
        
        # Кнопка выбора видео для фона
        self.bg_video_btn = QPushButton("Выбрать...")
        self.bg_video_btn.setFixedWidth(100)
        self.bg_video_btn.clicked.connect(self._choose_background_video)
        bg_video_layout.addWidget(self.bg_video_btn)
        
        # Кнопка очистки выбора видео
        self.bg_video_clear_btn = QPushButton("Очистить")
        self.bg_video_clear_btn.setFixedWidth(100)
        self.bg_video_clear_btn.clicked.connect(self._clear_background_video)
        self.bg_video_clear_btn.setEnabled(False)  # Изначально неактивна
        bg_video_layout.addWidget(self.bg_video_clear_btn)
        
        videos_group_layout.addWidget(bg_video_widget)
        
        # Добавляем метку для отображения имени выбранного видео фона
        self.bg_video_name_label = QLabel("Не выбрано")
        self.bg_video_name_label.setAlignment(Qt.AlignCenter)
        self.bg_video_name_label.setStyleSheet("color: #999999; font-style: italic;")
        videos_group_layout.addWidget(self.bg_video_name_label)
        
        # Добавляем разделитель между фоном и watermark
        videos_group_layout.addSpacing(10)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #555555;")
        videos_group_layout.addWidget(separator)
        videos_group_layout.addSpacing(10)
        
        # === ВЫБОР ВИДЕО WATERMARK ===
        wm_video_widget = QWidget()
        wm_video_layout = QHBoxLayout(wm_video_widget)
        wm_video_layout.setContentsMargins(0, 0, 0, 0)
        wm_video_layout.setSpacing(10)
        wm_video_label = QLabel("Watermark видео:")
        wm_video_layout.addWidget(wm_video_label)
        wm_video_layout.addStretch(1)
        self.wm_video_btn = QPushButton("Выбрать...")
        self.wm_video_btn.setFixedWidth(100)
        self.wm_video_btn.clicked.connect(self._choose_watermark_video)
        wm_video_layout.addWidget(self.wm_video_btn)
        self.wm_video_clear_btn = QPushButton("Очистить")
        self.wm_video_clear_btn.setFixedWidth(100)
        self.wm_video_clear_btn.clicked.connect(self._clear_watermark_video)
        self.wm_video_clear_btn.setEnabled(False)
        wm_video_layout.addWidget(self.wm_video_clear_btn)
        videos_group_layout.addWidget(wm_video_widget)
        self.wm_video_name_label = QLabel("Не выбрано")
        self.wm_video_name_label.setAlignment(Qt.AlignCenter)
        self.wm_video_name_label.setStyleSheet("color: #999999; font-style: italic;")
        videos_group_layout.addWidget(self.wm_video_name_label)
        
        # Добавляем группу видео в правый столбец
        right_layout.addWidget(videos_group)
        
        right_layout.addStretch(1)
        main_layout.addWidget(right_panel, 1)

    def _on_frame_toggled(self, checked):
        """Обработчик включения/выключения рамки."""
        self.frame_enabled = checked
        self._schedule_preview_update()
        
    def _on_crop_top_slider_changed(self, value):
        """Обработчик изменения значения верхней границы рамки через слайдер."""
        # Устанавливаем значение в пикселях
        self.crop_top_value = value
        # Обновляем поле ввода верхней границы, блокируя сигнал чтобы избежать рекурсии
        self.crop_top_input.blockSignals(True)
        self.crop_top_input.setText(str(value))
        self.crop_top_input.blockSignals(False)
        
        # Если включена синхронизация, обновляем значение нижней границы
        if self.crop_sync:
            self.crop_bottom_value = value
            self.crop_bottom_slider.blockSignals(True)
            self.crop_bottom_slider.setValue(value)
            self.crop_bottom_slider.blockSignals(False)
            self.crop_bottom_input.blockSignals(True)
            self.crop_bottom_input.setText(str(value))
            self.crop_bottom_input.blockSignals(False)
        
        # Если мы не перетаскиваем слайдер, обновляем превью
        if not self.slider_being_dragged:
            self._schedule_preview_update()
        
    def _on_crop_top_input_changed(self, text):
        """Обработчик изменения значения верхней границы рамки через поле ввода."""
        if not text:
            return
        try:
            value = int(text)
            if 0 <= value <= self.max_crop_per_side:
                self.crop_top_value = value
                # Обновляем слайдер, блокируя сигнал чтобы избежать рекурсии
                self.crop_top_slider.blockSignals(True)
                self.crop_top_slider.setValue(value)
                self.crop_top_slider.blockSignals(False)
                
                # Если включена синхронизация, обновляем значение нижней границы
                if self.crop_sync:
                    self.crop_bottom_value = value
                    self.crop_bottom_slider.blockSignals(True)
                    self.crop_bottom_slider.setValue(value)
                    self.crop_bottom_slider.blockSignals(False)
                    self.crop_bottom_input.blockSignals(True)
                    self.crop_bottom_input.setText(str(value))
                    self.crop_bottom_input.blockSignals(False)
                
                self._schedule_preview_update()
        except ValueError:
            pass
    
    def _on_flip_toggled(self, checked):
        """Обработчик включения/выключения отражения."""
        self.flip_enabled = checked
        self._schedule_preview_update()
        
    def _on_brightness_toggled(self, checked):
        """Обработчик включения/выключения затемнения."""
        self.brightness_enabled = checked
        self._schedule_preview_update()
        
    def _on_brightness_changed(self, value):
        """Обработчик изменения яркости через слайдер."""
        self.brightness_value = value
        # Обновляем поле ввода, блокируя сигнал чтобы избежать рекурсии
        self.brightness_input.blockSignals(True)
        self.brightness_input.setText(str(value))
        self.brightness_input.blockSignals(False)
        
        # Если мы не перетаскиваем слайдер, обновляем превью
        # Если перетаскиваем, то обновляем быстрое представление или ничего не делаем
        if not self.slider_being_dragged:
            self._schedule_preview_update()
        
    def _on_brightness_input_changed(self, text):
        """Обработчик изменения яркости через поле ввода."""
        if not text:
            return
        try:
            value = int(text)
            if 0 <= value <= 100:
                self.brightness_value = value
                # Обновляем слайдер, блокируя сигнал чтобы избежать рекурсии
                self.brightness_slider.blockSignals(True)
                self.brightness_slider.setValue(value)
                self.brightness_slider.blockSignals(False)
                self._schedule_preview_update()
        except ValueError:
            pass

    def _on_slider_pressed(self):
        """Обработчик нажатия на слайдер"""
        self.slider_being_dragged = True
        # Отмечаем статус, что идет перетаскивание
        self.status.setText('Перетащите для изменения...')
        
    def _on_slider_released(self):
        """Обработчик отпускания слайдера"""
        self.slider_being_dragged = False
        # Сразу обновляем превью без задержки
        self.status.setText('Обновление превью...')
        self.show_preview_frame()

    def _schedule_preview_update(self):
        """Планирует обновление превью с задержкой для дебаунсинга"""
        # Показываем пользователю, что превью скоро обновится
        if not self.is_preview_generating:
            self.status.setText('Планирование обновления превью...')
            
        # Полностью убираем задержку для мгновенного отклика
        self._delayed_preview_update()

    def _delayed_preview_update(self):
        """Вызывается после дебаунсинга для обновления превью"""
        self.show_preview_frame()

    def _cancel_processing(self):
        """Отменяет текущую обработку видео"""
        if self._ffmpeg_video_worker and self._ffmpeg_video_worker.isRunning():
            self._ffmpeg_video_worker.stop()
            self.status.setText('Обработка отменена')
            self.progress.setVisible(False)
            self.unique_btn.setEnabled(True)
            self.cancel_btn.setVisible(False)

    def choose_file(self):
        """Открывает диалог выбора видеофайла"""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите видео', 
            self.input_dir, 
            'Видео (*.mp4 *.mov *.avi *.webm *.mkv)'
        )
        if path:
            self.input_path = path
            self.file_btn.setText(os.path.basename(path))
            self.unique_btn.setEnabled(True)
            
            # Определяем размеры видео
            self._get_video_dimensions(path)
            
            # Показываем превью
            self.show_preview_frame()
        else:
            self.unique_btn.setEnabled(False)
            
    def _get_video_dimensions(self, video_path):
        """Получает размеры видео с помощью ffprobe"""
        try:
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-select_streams', 'v:0', 
                '-show_entries', 'stream=width,height', 
                '-of', 'csv=s=x:p=0', 
                video_path
            ]
            output = subprocess.check_output(cmd).decode('utf-8').strip()
            width, height = map(int, output.split('x'))
            
            self.video_width = width
            self.video_height = height
            # Устанавливаем максимум для ползунков как 49% от высоты видео
            self.max_crop_per_side = int(height * 0.49)
            
            # Обновляем максимальные значения ползунков
            self.crop_top_slider.setMaximum(self.max_crop_per_side)
            self.crop_bottom_slider.setMaximum(self.max_crop_per_side)
            
            # Обновляем валидаторы полей ввода
            self.crop_top_input.setValidator(QIntValidator(0, self.max_crop_per_side))
            self.crop_bottom_input.setValidator(QIntValidator(0, self.max_crop_per_side))
            
            # Если текущие значения больше максимальных, корректируем их
            if self.crop_top_value > self.max_crop_per_side:
                self.crop_top_value = self.max_crop_per_side
                self.crop_top_slider.setValue(self.max_crop_per_side)
                self.crop_top_input.setText(str(self.max_crop_per_side))
                
            if self.crop_bottom_value > self.max_crop_per_side:
                self.crop_bottom_value = self.max_crop_per_side
                self.crop_bottom_slider.setValue(self.max_crop_per_side)
                self.crop_bottom_input.setText(str(self.max_crop_per_side))
                
            # Обновляем статус
            self.status.setText(f'Видео загружено: {width}x{height} пикселей')
            
        except Exception as e:
            self.show_error(f"Не удалось определить размеры видео: {str(e)}")
            # Установим значения по умолчанию
            self.video_width = 1920
            self.video_height = 1080
            self.max_crop_per_side = 500
            
    def _on_crop_bottom_slider_changed(self, value):
        """Обработчик изменения значения нижней границы рамки через слайдер."""
        # Устанавливаем значение в пикселях
        self.crop_bottom_value = value
        # Обновляем поле ввода нижней границы, блокируя сигнал чтобы избежать рекурсии
        self.crop_bottom_input.blockSignals(True)
        self.crop_bottom_input.setText(str(value))
        self.crop_bottom_input.blockSignals(False)
        
        # Если включена синхронизация, обновляем значение верхней границы
        if self.crop_sync:
            self.crop_top_value = value
            self.crop_top_slider.blockSignals(True)
            self.crop_top_slider.setValue(value)
            self.crop_top_slider.blockSignals(False)
            self.crop_top_input.blockSignals(True)
            self.crop_top_input.setText(str(value))
            self.crop_top_input.blockSignals(False)
        
        # Если мы не перетаскиваем слайдер, обновляем превью
        if not self.slider_being_dragged:
            self._schedule_preview_update()
        
    def _on_crop_bottom_input_changed(self, text):
        """Обработчик изменения значения нижней границы рамки через поле ввода."""
        if not text:
            return
        try:
            value = int(text)
            if 0 <= value <= self.max_crop_per_side:
                self.crop_bottom_value = value
                # Обновляем слайдер, блокируя сигнал чтобы избежать рекурсии
                self.crop_bottom_slider.blockSignals(True)
                self.crop_bottom_slider.setValue(value)
                self.crop_bottom_slider.blockSignals(False)
                
                # Если включена синхронизация, обновляем значение верхней границы
                if self.crop_sync:
                    self.crop_top_value = value
                    self.crop_top_slider.blockSignals(True)
                    self.crop_top_slider.setValue(value)
                    self.crop_top_slider.blockSignals(False)
                    self.crop_top_input.blockSignals(True)
                    self.crop_top_input.setText(str(value))
                    self.crop_top_input.blockSignals(False)
                
                self._schedule_preview_update()
        except ValueError:
            pass

    def _on_crop_sync_changed(self, checked):
        """Обработчик изменения состояния чекбокса синхронизации."""
        self.crop_sync = checked
        
        # При включении синхронизации устанавливаем нижнюю границу равной верхней
        if checked:
            self.crop_bottom_value = self.crop_top_value
            self.crop_bottom_slider.blockSignals(True)
            self.crop_bottom_slider.setValue(self.crop_top_value)
            self.crop_bottom_slider.blockSignals(False)
            self.crop_bottom_input.blockSignals(True)
            self.crop_bottom_input.setText(str(self.crop_top_value))
            self.crop_bottom_input.blockSignals(False)
            self._schedule_preview_update()

    def get_effects_vf(self):
        """Возвращает строку фильтра для ffmpeg с учетом выбранных эффектов."""
        filters = []
        simple_filters = []
        if self.flip_enabled:
            simple_filters.append("hflip")
        if self.brightness_enabled and self.brightness_value > 0:
            brightness_normalized = -self.brightness_value / 400.0
            simple_filters.append(f"eq=brightness={brightness_normalized:.2f}")
        filter_prefix = ""
        if simple_filters:
            filter_prefix = ",".join(simple_filters) + ","
        if self.frame_enabled:
            bg_darkness = -self.background_darkness_value / 100.0 * 0.7 if self.background_darkness_value > 0 else 0
            blur_radius = self.background_blur_value if self.background_blur_value > 0 else 1
            bg_scale = self.background_scale_value / 100.0
            top_crop = self.crop_top_value
            bottom_crop = self.crop_bottom_value
            video_w = getattr(self, 'video_width', None)
            video_h = getattr(self, 'video_height', None)
            if not video_w or not video_h:
                return None
            # watermark + фон
            if self.watermark_video_path and os.path.exists(self.watermark_video_path) and self.background_video_path and os.path.exists(self.background_video_path):
                filter_complex = (
                    f"{filter_prefix}"
                    f"[1:v]scale={video_w}:ih*{bg_scale:.2f},boxblur=luma_radius={blur_radius}:luma_power=2,eq=brightness={bg_darkness:.2f},crop={video_w}:{video_h}:0:0[bg];"
                    f"[2:v]format=rgba,colorchannelmixer=aa=0.5,scale={video_w}:{video_h}[wm];"
                    f"[bg][wm]overlay=(W-w)/2:(H-h)/2[bgwm];"
                    f"[0:v]crop=iw:ih-{top_crop}-{bottom_crop}:0:{top_crop}[fg];"
                    f"[bgwm][fg]overlay=0:{top_crop}"
                )
                return filter_complex
            # только watermark
            elif self.watermark_video_path and os.path.exists(self.watermark_video_path):
                total_crop_height = top_crop + bottom_crop
                new_height = f"ih-{total_crop_height}"
                crop_y_position = top_crop
                vertical_offset = (bottom_crop - top_crop) // 2
                filter_complex = (
                    f"{filter_prefix}"
                    f"[0:v]split[main][bg];"
                    f"[bg]scale=iw*{bg_scale:.2f}:ih*{bg_scale:.2f},boxblur=luma_radius={blur_radius}:luma_power=2,eq=brightness={bg_darkness:.2f}[bg_blurred];"
                    f"[1:v]format=rgba,colorchannelmixer=aa=0.5,scale={video_w}:{video_h}[wm];"
                    f"[bg_blurred][wm]overlay=(W-w)/2:(H-h)/2[bgwm];"
                    f"[main]crop=iw:{new_height}:0:{crop_y_position}[fg];"
                    f"[bgwm][fg]overlay=(W-w)/2:(H-h)/2-{vertical_offset}[combined];"
                    f"[combined]crop=iw/({bg_scale:.2f}):ih/({bg_scale:.2f}):iw/2-iw/(2*{bg_scale:.2f}):ih/2-ih/(2*{bg_scale:.2f})"
                )
                return filter_complex
            # только фон
            elif self.background_video_path and os.path.exists(self.background_video_path):
                filter_complex = (
                    f"{filter_prefix}"
                    f"[1:v]scale={video_w}:ih*{bg_scale:.2f},boxblur=luma_radius={blur_radius}:luma_power=2,eq=brightness={bg_darkness:.2f},crop={video_w}:{video_h}:0:0[bg];"
                    f"[0:v]crop=iw:ih-{top_crop}-{bottom_crop}:0:{top_crop}[fg];"
                    f"[bg][fg]overlay=0:{top_crop}"
                )
                return filter_complex
            # ни фон, ни watermark
            else:
                total_crop_height = top_crop + bottom_crop
                new_height = f"ih-{total_crop_height}"
                crop_y_position = top_crop
                vertical_offset = (bottom_crop - top_crop) // 2
                filter_complex = (
                    f"{filter_prefix}split[main][bg];"
                    f"[bg]scale=iw*{bg_scale:.2f}:ih*{bg_scale:.2f},boxblur=luma_radius={blur_radius}:luma_power=2,eq=brightness={bg_darkness:.2f}[bg_blurred];"
                    f"[main]crop=iw:{new_height}:0:{crop_y_position}[fg];"
                    f"[bg_blurred][fg]overlay=(W-w)/2:(H-h)/2-{vertical_offset}[combined];"
                    f"[combined]crop=iw/({bg_scale:.2f}):ih/({bg_scale:.2f}):iw/2-iw/(2*{bg_scale:.2f}):ih/2-ih/(2*{bg_scale:.2f})"
                )
                return filter_complex
        if simple_filters:
            return ",".join(simple_filters)
        return None

    def show_preview_frame(self):
        """Генерирует превью текущих настроек"""
        if not self.input_path:
            return
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.stop()
        self.is_preview_generating = True
        self.status.setText('Генерация превью...')
        filter_str = self.get_effects_vf()
        preview_path = os.path.join(self.temp_dir, 'preview.png')
        # watermark + фон
        if self.frame_enabled and self.watermark_video_path and os.path.exists(self.watermark_video_path) and self.background_video_path and os.path.exists(self.background_video_path):
            cmd = ['ffmpeg', '-y', '-ss', self.frame_time, '-i', self.input_path,
                   '-ss', self.frame_time, '-i', self.background_video_path,
                   '-ss', self.frame_time, '-i', self.watermark_video_path,
                   '-filter_complex', filter_str, '-frames:v', '1', '-update', '1', preview_path]
        # только watermark
        elif self.frame_enabled and self.watermark_video_path and os.path.exists(self.watermark_video_path):
            cmd = ['ffmpeg', '-y', '-ss', self.frame_time, '-i', self.input_path,
                   '-ss', self.frame_time, '-i', self.watermark_video_path,
                   '-filter_complex', filter_str, '-frames:v', '1', '-update', '1', preview_path]
        # только фон
        elif self.frame_enabled and self.background_video_path and os.path.exists(self.background_video_path):
            cmd = ['ffmpeg', '-y', '-ss', self.frame_time, '-i', self.input_path, 
                   '-ss', self.frame_time, '-i', self.background_video_path,
                   '-filter_complex', filter_str, '-frames:v', '1', '-update', '1', preview_path]
        else:
            cmd = create_ffmpeg_command(self.input_path, preview_path, filter_str, is_preview=True, frame_time=self.frame_time)
        self._preview_worker = FFmpegProcessor(cmd, output_path=preview_path)
        self._preview_worker.finished.connect(lambda _: self._on_preview_ready(preview_path))
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()

    def _on_preview_ready(self, preview_path):
        """Вызывается, когда превью готово"""
        self.is_preview_generating = False
        self.status.setText(f'Превью обновлено (кадр: {self.frame_time})')
        self.set_preview(preview_path)
        
    def _on_preview_error(self, error):
        """Вызывается при ошибке генерации превью"""
        self.is_preview_generating = False
        self.show_error(error)

    def set_preview(self, preview_path):
        """Устанавливает превью в интерфейсе"""
        if not os.path.exists(preview_path):
            self.show_error('Файл превью не найден')
            return
            
        # Очищаем предыдущее изображение, если оно было
        if self.preview_label._pixmap:
            self.preview_label._pixmap = None
            
        pix = QPixmap(preview_path)
        if pix.isNull():
            self.show_error('Не удалось загрузить превью')
            return
            
        self.preview_label.setPixmap(pix)

    def process_unique_video(self):
        """Обрабатывает видео с выбранными эффектами"""
        if not self.input_path:
            return
        filter_str = self.get_effects_vf()
        if not filter_str:
            self.show_error('Пожалуйста, выберите хотя бы один эффект для уникализации')
            return
        base_name = os.path.basename(self.input_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join(self.output_dir, f"{name}_unique{ext}")
        # watermark + фон
        if self.frame_enabled and self.watermark_video_path and os.path.exists(self.watermark_video_path) and self.background_video_path and os.path.exists(self.background_video_path):
            cmd = ['ffmpeg', '-y', '-i', self.input_path, '-i', self.background_video_path, '-i', self.watermark_video_path,
                   '-filter_complex', filter_str, '-c:a', 'copy', output_path]
        # только watermark
        elif self.frame_enabled and self.watermark_video_path and os.path.exists(self.watermark_video_path):
            cmd = ['ffmpeg', '-y', '-i', self.input_path, '-i', self.watermark_video_path,
                   '-filter_complex', filter_str, '-c:a', 'copy', output_path]
        # только фон
        elif self.frame_enabled and self.background_video_path and os.path.exists(self.background_video_path):
            cmd = ['ffmpeg', '-y', '-i', self.input_path, '-i', self.background_video_path,
                   '-filter_complex', filter_str, '-c:a', 'copy', output_path]
        else:
            cmd = create_ffmpeg_command(self.input_path, output_path, filter_str)
        self.run_ffmpeg_with_progress(cmd, output_path)

    def run_ffmpeg_with_progress(self, cmd, output_path):
        """Запускает FFmpeg с отображением прогресса"""
        self.status.setText('Обработка видео...')
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.unique_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        
        # Запускаем FFmpeg в отдельном потоке
        self._ffmpeg_video_worker = FFmpegProcessor(cmd, output_path, parse_progress=True)
        self._ffmpeg_video_worker.progress.connect(self._on_ffmpeg_progress)
        self._ffmpeg_video_worker.finished.connect(self._on_video_ready)
        self._ffmpeg_video_worker.error.connect(self._on_video_error)
        self._ffmpeg_video_worker.start()

    def _on_ffmpeg_progress(self, percent):
        """Обновляет прогресс-бар"""
        self.progress.setValue(percent)

    def _on_video_ready(self, path):
        """Видео обработано успешно"""
        self.status.setText(f'Готово: {os.path.basename(path)}')
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.unique_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        
        # Очищаем временные файлы
        cleanup_temp_files(self.temp_dir)

    def _on_video_error(self, error):
        """Ошибка при обработке видео"""
        self.status.setText('Ошибка: ' + error)
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.unique_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)

    def resizeEvent(self, event):
        """Обработчик изменения размера виджета"""
        # Просто обновляем превью, если оно загружено
        if self.preview_label._pixmap:
            self.preview_label.update()
        super().resizeEvent(event)

    def show_error(self, error):
        """Отображает сообщение об ошибке"""
        print('Ошибка:', error)
        self.status.setText('Ошибка: ' + error) 

    def _slider_mouse_press_event(self, slider, event):
        """Кастомный обработчик нажатия на слайдер для перемещения к месту клика"""
        from PyQt5.QtWidgets import QStyle, QStyleOptionSlider
        from PyQt5.QtCore import QPoint
        
        # Создаем объект опций стиля для слайдера
        opt = QStyleOptionSlider()
        slider.initStyleOption(opt)
        
        # Получаем прямоугольную область дорожки слайдера
        groove_rect = slider.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, slider)
        handle_rect = slider.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, slider)
        
        # Вычисляем позицию клика относительно границ слайдера
        if slider.orientation() == Qt.Horizontal:
            slider_length = groove_rect.width()
            slider_pos = event.x() - groove_rect.x()
            pos_percentage = slider_pos / slider_length
        else:
            slider_length = groove_rect.height()
            slider_pos = event.y() - groove_rect.y()
            pos_percentage = 1 - slider_pos / slider_length
            
        # Вычисляем значение в месте клика
        value_range = slider.maximum() - slider.minimum()
        click_value = slider.minimum() + round(value_range * pos_percentage)
        
        # Проверяем, было ли нажатие на ручку или на дорожку
        if handle_rect.contains(event.pos()):
            # Нажатие на ручку - продолжаем стандартное перетаскивание
            self._on_slider_pressed()
            QSlider.mousePressEvent(slider, event)
        else:
            # Нажатие на дорожку - перемещаем слайдер к месту клика и начинаем перетаскивание
            slider.setValue(click_value)
            # Переносим событие в позицию ручки, чтобы можно было продолжить перетаскивание
            center_handle = QPoint(handle_rect.center())
            event_moved = type(event)(event.type(), center_handle, event.button(), event.buttons(), event.modifiers())
            self._on_slider_pressed()
            QSlider.mousePressEvent(slider, event_moved) 

    def _on_bg_darkness_changed(self, value):
        """Обработчик изменения затемнения фона через слайдер."""
        self.background_darkness_value = value
        # Обновляем поле ввода, блокируя сигнал чтобы избежать рекурсии
        self.bg_darkness_input.blockSignals(True)
        self.bg_darkness_input.setText(str(value))
        self.bg_darkness_input.blockSignals(False)
        
        # Если мы не перетаскиваем слайдер, обновляем превью
        # Если перетаскиваем, то обновляем быстрое представление или ничего не делаем
        if not self.slider_being_dragged:
            self._schedule_preview_update()
        
    def _on_bg_darkness_input_changed(self, text):
        """Обработчик изменения затемнения фона через поле ввода."""
        if not text:
            return
        try:
            value = int(text)
            if 0 <= value <= 100:
                self.background_darkness_value = value
                # Обновляем слайдер, блокируя сигнал чтобы избежать рекурсии
                self.bg_darkness_slider.blockSignals(True)
                self.bg_darkness_slider.setValue(value)
                self.bg_darkness_slider.blockSignals(False)
                self._schedule_preview_update()
        except ValueError:
            pass 

    def _on_bg_blur_changed(self, value):
        """Обработчик изменения размытия фона через слайдер."""
        self.background_blur_value = value
        # Обновляем поле ввода, блокируя сигнал чтобы избежать рекурсии
        self.bg_blur_input.blockSignals(True)
        self.bg_blur_input.setText(str(value))
        self.bg_blur_input.blockSignals(False)
        
        # Если мы не перетаскиваем слайдер, обновляем превью
        # Если перетаскиваем, то обновляем быстрое представление или ничего не делаем
        if not self.slider_being_dragged:
            self._schedule_preview_update()
        
    def _on_bg_blur_input_changed(self, text):
        """Обработчик изменения размытия фона через поле ввода."""
        if not text:
            return
        try:
            value = int(text)
            if 0 <= value <= 100:
                self.background_blur_value = value
                # Обновляем слайдер, блокируя сигнал чтобы избежать рекурсии
                self.bg_blur_slider.blockSignals(True)
                self.bg_blur_slider.setValue(value)
                self.bg_blur_slider.blockSignals(False)
                self._schedule_preview_update()
        except ValueError:
            pass

    def _on_bg_scale_changed(self, value):
        """Обработчик изменения масштаба фона через слайдер."""
        self.background_scale_value = value
        # Обновляем поле ввода, блокируя сигнал чтобы избежать рекурсии
        self.bg_scale_input.blockSignals(True)
        self.bg_scale_input.setText(str(value))
        self.bg_scale_input.blockSignals(False)
        
        # Если мы не перетаскиваем слайдер, обновляем превью
        # Если перетаскиваем, то обновляем быстрое представление или ничего не делаем
        if not self.slider_being_dragged:
            self._schedule_preview_update()
        
    def _on_bg_scale_input_changed(self, text):
        """Обрабатывает изменение значения в поле ввода масштаба фона."""
        try:
            value = int(text)
            if value != self.background_scale_value:
                # Проверяем на валидность значения
                if 100 <= value <= 200:
                    self.background_scale_value = value
                    # Блокируем отправку сигнала valueChanged при программном изменении
                    self.bg_scale_slider.blockSignals(True)
                    self.bg_scale_slider.setValue(value)
                    self.bg_scale_slider.blockSignals(False)
                    # Планируем обновление превью
                    self._schedule_preview_update()
        except ValueError:
            pass
    
    def _choose_background_video(self):
        """Позволяет пользователю выбрать видео для фона рамки"""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Видео файлы (*.mp4 *.avi *.mkv *.mov *.webm *.wmv)")
        
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.background_video_path = selected_files[0]
                self.bg_video_name_label.setText(os.path.basename(self.background_video_path))
                self.bg_video_clear_btn.setEnabled(True)
                # Обновляем превью
                self._schedule_preview_update()
    
    def _clear_background_video(self):
        """Очищает выбранное видео фона"""
        self.background_video_path = ''
        self.bg_video_name_label.setText("Не выбрано")
        self.bg_video_clear_btn.setEnabled(False)
        # Обновляем превью
        self._schedule_preview_update()

    def _choose_watermark_video(self):
        """Позволяет выбрать watermark-видео"""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("Видео файлы (*.mp4 *.avi *.mkv *.mov *.webm *.wmv)")
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.watermark_video_path = selected_files[0]
                self.wm_video_name_label.setText(os.path.basename(self.watermark_video_path))
                self.wm_video_clear_btn.setEnabled(True)
                self._schedule_preview_update()
    
    def _clear_watermark_video(self):
        """Очищает выбранное watermark-видео"""
        self.watermark_video_path = ''
        self.wm_video_name_label.setText("Не выбрано")
        self.wm_video_clear_btn.setEnabled(False)
        self._schedule_preview_update()

    def _next_preview_frame(self):
        """Обработчик нажатия на кнопку для выбора другого кадра превью"""
        if not self.input_path or not os.path.exists(self.input_path):
            return
            
        # Изменяем время кадра, используем простую схему переключения между 5 точками видео
        time_points = ["00:00:00.2", "00:00:02.0", "00:00:05.0", "00:00:10.0", "00:00:30.0"]
        current_index = time_points.index(self.frame_time) if self.frame_time in time_points else 0
        next_index = (current_index + 1) % len(time_points)
        self.frame_time = time_points[next_index]
        
        # Обновляем превью с новым кадром
        self.show_preview_frame()