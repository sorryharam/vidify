"""
Экран для конвертации видео без потери качества.
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QSizePolicy,
    QProgressBar, QFrame, QLineEdit, QComboBox, QFormLayout, QGroupBox, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from vidify.core.video_processor import (
    FFmpegProcessor, create_ffmpeg_command, check_ffmpeg_available, cleanup_temp_files
)
from vidify.ui.components.widgets import AspectFrameLabel


class VideoConvertScreen(QWidget):
    """Экран для конвертации видео без потери качества."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("videoConvertTab")
        
        # Пути для организации файлов
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data'))
        self.input_dir = os.path.join(base_path, 'input')
        self.temp_dir = os.path.join(base_path, 'temp')
        self.output_dir = os.path.join(base_path, 'output')
        
        # Создаем директории если не существуют
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Переменные состояния
        self.input_path = ''
        self.output_path = ''
        self._ffmpeg_convert_worker = None
        self.output_format = 'mp4'
        
        # Доступные форматы
        self.video_formats = {
            'mp4': {
                'extension': 'mp4',
                'codec': 'libx264',
                'params': ['-preset', 'slow', '-crf', '0']
            },
            'mkv': {
                'extension': 'mkv',
                'codec': 'libx264',
                'params': ['-preset', 'slow', '-crf', '0']
            },
            'avi': {
                'extension': 'avi',
                'codec': 'huffyuv',
                'params': []
            },
            'mov': {
                'extension': 'mov',
                'codec': 'prores_ks',
                'params': ['-profile:v', '4444']
            },
            'webm': {
                'extension': 'webm',
                'codec': 'libvpx-vp9',
                'params': ['-lossless', '1']
            }
        }
        
        # Настройки копирования аудио
        self.copy_audio = True
        
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
        """Инициализация интерфейса конвертера видео."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)
        
        # Левая панель с настройками
        left_panel = QFrame()
        left_panel.setObjectName('leftPanel')
        left_panel.setFrameShape(QFrame.NoFrame)
        left_layout = QVBoxLayout(left_panel)
        
        # Стили для групп
        group_style = """
            QGroupBox {
                background-color: #2a2a3a;
                border-radius: 8px;
                padding: 15px;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """
        
        # Группа настроек формата
        format_group = QGroupBox("Формат конвертации")
        format_group.setStyleSheet(group_style)
        format_layout = QFormLayout(format_group)
        format_layout.setContentsMargins(15, 25, 15, 15)
        format_layout.setSpacing(15)
        
        # Выбор формата
        self.format_combo = QComboBox()
        for fmt in self.video_formats.keys():
            self.format_combo.addItem(fmt.upper(), fmt)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addRow("Выходной формат:", self.format_combo)
        
        # Чекбокс копирования аудио
        self.audio_checkbox = QCheckBox("Копировать аудио без перекодирования")
        self.audio_checkbox.setChecked(True)
        self.audio_checkbox.toggled.connect(self._on_audio_copy_toggled)
        format_layout.addRow("", self.audio_checkbox)
        
        # Информация о видео
        self.info_label = QLabel("Загрузите видео для конвертации")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignLeft)
        format_layout.addRow("Информация:", self.info_label)
        
        left_layout.addWidget(format_group)
        
        # Группа дополнительные настройки lossless
        lossless_group = QGroupBox("Lossless настройки")
        lossless_group.setStyleSheet(group_style)
        lossless_layout = QVBoxLayout(lossless_group)
        lossless_layout.setContentsMargins(15, 25, 15, 15)
        
        # Примечание о кодеках
        note_label = QLabel(
            "Для каждого формата выбран наилучший lossless кодек:\n"
            "• MP4: H.264 (CRF 0)\n"
            "• MKV: H.264 (CRF 0)\n"
            "• AVI: HuffYUV\n"
            "• MOV: ProRes 4444\n"
            "• WEBM: VP9 Lossless"
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("font-size: 12px;")
        lossless_layout.addWidget(note_label)
        
        left_layout.addWidget(lossless_group)
        left_layout.addStretch(1)
        
        main_layout.addWidget(left_panel, 1)
        
        # Центральная колонка с превью и кнопками
        center_panel = QFrame()
        center_panel.setObjectName('centerPanel')
        center_panel.setFrameShape(QFrame.NoFrame)
        center_layout = QVBoxLayout(center_panel)
        
        # Виджет превью
        self.preview_container = QWidget()
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        
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
        
        self.convert_btn = QPushButton('Конвертировать')
        self.convert_btn.clicked.connect(self.convert_video)
        self.convert_btn.setEnabled(False)
        
        # Кнопка отмены обработки
        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.clicked.connect(self._cancel_processing)
        self.cancel_btn.setVisible(False)
        
        # Кнопка просмотра папки с результатом
        self.folder_btn = QPushButton('Открыть папку')
        self.folder_btn.clicked.connect(self._open_output_folder)
        
        btn_layout.addWidget(self.file_btn)
        btn_layout.addWidget(self.convert_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.folder_btn)
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
        
        main_layout.addWidget(center_panel, 2)
    
    def _on_format_changed(self, index):
        """Обработчик изменения формата конвертации."""
        self.output_format = self.format_combo.currentData()
    
    def _on_audio_copy_toggled(self, checked):
        """Обработчик переключения копирования аудио."""
        self.copy_audio = checked
    
    def choose_file(self):
        """Открывает диалог выбора видеофайла."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите видео', 
            self.input_dir, 
            'Видео (*.mp4 *.mov *.avi *.webm *.mkv)'
        )
        if path:
            self.input_path = path
            self.file_btn.setText(os.path.basename(path))
            self.convert_btn.setEnabled(True)
            
            # Определяем размер видео и показываем информацию
            self._get_video_info(path)
            
            # Показываем превью
            self._show_preview_frame(path)
        else:
            self.convert_btn.setEnabled(False)
    
    def _get_video_info(self, video_path):
        """Получает информацию о видео с помощью ffprobe."""
        try:
            # Получаем размеры
            cmd_dimensions = [
                'ffprobe', 
                '-v', 'error', 
                '-select_streams', 'v:0', 
                '-show_entries', 'stream=width,height', 
                '-of', 'csv=s=x:p=0', 
                video_path
            ]
            dimensions = subprocess.check_output(cmd_dimensions).decode('utf-8').strip()
            width, height = map(int, dimensions.split('x'))
            
            # Получаем кодек и битрейт
            cmd_codec = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,bit_rate',
                '-of', 'default=noprint_wrappers=1',
                video_path
            ]
            codec_info = subprocess.check_output(cmd_codec).decode('utf-8').strip()
            
            # Получаем информацию о формате
            cmd_format = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=format_name,size',
                '-of', 'default=noprint_wrappers=1',
                video_path
            ]
            format_info = subprocess.check_output(cmd_format).decode('utf-8').strip()
            
            # Парсим данные и формируем информацию
            codec_name = "неизвестно"
            bitrate = "неизвестно"
            format_name = "неизвестно"
            size_bytes = 0
            
            for line in codec_info.split('\n'):
                if line.startswith('codec_name='):
                    codec_name = line.split('=')[1]
                elif line.startswith('bit_rate='):
                    try:
                        bitrate_val = int(line.split('=')[1])
                        bitrate = f"{bitrate_val / 1000000:.2f} Мбит/с"
                    except (ValueError, IndexError):
                        pass
            
            for line in format_info.split('\n'):
                if line.startswith('format_name='):
                    format_name = line.split('=')[1]
                elif line.startswith('size='):
                    try:
                        size_bytes = int(line.split('=')[1])
                        size_mb = size_bytes / (1024 * 1024)
                        if size_mb > 1024:
                            size = f"{size_mb / 1024:.2f} ГБ"
                        else:
                            size = f"{size_mb:.2f} МБ"
                    except (ValueError, IndexError):
                        size = "неизвестно"
            
            # Обновляем информацию
            info_text = f"Размер: {width}x{height}\nКодек: {codec_name}\nБитрейт: {bitrate}\nФормат: {format_name}\nРазмер файла: {size}"
            self.info_label.setText(info_text)
            
        except Exception as e:
            self.show_error(f"Не удалось получить информацию о видео: {str(e)}")
            self.info_label.setText("Ошибка получения информации")
    
    def _show_preview_frame(self, video_path):
        """Показывает превью кадра из видео."""
        preview_path = os.path.join(self.temp_dir, 'convert_preview.png')
        try:
            # Команда для получения кадра
            cmd = [
                'ffmpeg', '-y', '-ss', '00:00:00.5', 
                '-i', video_path, 
                '-frames:v', '1', 
                preview_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Устанавливаем превью
            if os.path.exists(preview_path):
                pixmap = QPixmap(preview_path)
                self.preview_label.setPixmap(pixmap)
            else:
                self.preview_label.setText("Не удалось создать превью")
        except Exception as e:
            self.show_error(f"Ошибка создания превью: {str(e)}")
            self.preview_label.setText("Ошибка превью")
    
    def convert_video(self):
        """Конвертирует видео в выбранный формат без потери качества."""
        if not self.input_path:
            self.show_error("Пожалуйста, выберите видео для конвертации")
            return
        
        # Генерируем имя выходного файла
        base_name = os.path.splitext(os.path.basename(self.input_path))[0]
        extension = self.video_formats[self.output_format]['extension']
        self.output_path = os.path.join(self.output_dir, f"{base_name}_lossless.{extension}")
        
        # Создаем команду для конвертации
        cmd = self._create_convert_command()
        
        # Запускаем конвертацию
        self._run_conversion(cmd)
    
    def _create_convert_command(self):
        """Создает команду ffmpeg для конвертации без потери качества."""
        cmd = ['ffmpeg', '-y', '-i', self.input_path]
        
        # Добавляем настройки видеокодека
        format_info = self.video_formats[self.output_format]
        cmd.extend(['-c:v', format_info['codec']])
        
        # Добавляем дополнительные параметры для кодека
        if format_info['params']:
            cmd.extend(format_info['params'])
        
        # Настройки аудио
        if self.copy_audio:
            cmd.extend(['-c:a', 'copy'])
        else:
            # Используем lossless аудиокодек
            if self.output_format == 'webm':
                cmd.extend(['-c:a', 'libopus', '-b:a', '192k'])
            else:
                cmd.extend(['-c:a', 'flac'])
        
        # Выходной файл
        cmd.append(self.output_path)
        
        return cmd
    
    def _run_conversion(self, cmd):
        """Запускает FFmpeg с отображением прогресса."""
        self.status.setText('Конвертация видео...')
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.convert_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        
        # Запускаем FFmpeg в отдельном потоке
        self._ffmpeg_convert_worker = FFmpegProcessor(cmd, self.output_path, parse_progress=True)
        self._ffmpeg_convert_worker.progress.connect(self._on_conversion_progress)
        self._ffmpeg_convert_worker.finished.connect(self._on_conversion_ready)
        self._ffmpeg_convert_worker.error.connect(self._on_conversion_error)
        self._ffmpeg_convert_worker.start()
    
    def _on_conversion_progress(self, percent):
        """Обновляет прогресс-бар при конвертации."""
        self.progress.setValue(percent)
    
    def _on_conversion_ready(self, path):
        """Вызывается, когда конвертация завершена."""
        self.status.setText(f'Готово: {os.path.basename(path)}')
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.convert_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        
        # Очищаем временные файлы
        cleanup_temp_files(self.temp_dir)
    
    def _on_conversion_error(self, error):
        """Вызывается при ошибке конвертации."""
        self.status.setText('Ошибка: ' + error)
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.convert_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
    
    def _cancel_processing(self):
        """Отменяет текущую обработку видео."""
        if self._ffmpeg_convert_worker and self._ffmpeg_convert_worker.isRunning():
            self._ffmpeg_convert_worker.stop()
            self.status.setText('Конвертация отменена')
            self.progress.setVisible(False)
            self.convert_btn.setEnabled(True)
            self.cancel_btn.setVisible(False)
    
    def _open_output_folder(self):
        """Открывает папку с результатами конвертации."""
        try:
            import platform
            import subprocess
            
            if platform.system() == "Windows":
                os.startfile(self.output_dir)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", self.output_dir], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", self.output_dir], check=True)
        except Exception as e:
            self.show_error(f"Не удалось открыть папку: {str(e)}")
    
    def show_error(self, error):
        """Отображает сообщение об ошибке."""
        print('Ошибка:', error)
        self.status.setText('Ошибка: ' + error) 