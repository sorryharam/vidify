"""
Модуль для скачивания видео с различных платформ.
"""
import re
import os
import sys
import json
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, Callable
from functools import lru_cache

import yt_dlp
from PyQt5.QtCore import QThread, pyqtSignal


class DownloadStatus(Enum):
    """Статус скачивания."""
    READY = "Готово"
    DOWNLOADING = "Скачивание..."
    CANCELED = "Отменено"
    PREPARE = "Подготовка..."
    ALREADY = "Уже идет скачивание"
    NO_URL = "Введите ссылку"
    FOLDER_CHOSEN = "Папка: {folder}"
    ERROR = "Ошибка: {error}"
    FINISHED = "Готово!"
    PREVIEW = "Получение информации..."


VIDEO_EXTS = ["mp4", "webm", "mkv", "mov", "avi"]


def is_valid_url(url: str) -> bool:
    """Проверяет валидность URL."""
    if not url:
        return False
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def setup_paths(base_dir_name: str = 'data') -> Tuple[Path, Path, Path]:
    """Создаёт и возвращает пути для input, output и temp папок."""
    base_path = Path(__file__).parent.parent / base_dir_name
    input_path = base_path / 'input'
    output_path = base_path / 'output'
    temp_path = base_path / 'temp'
    for path in (input_path, output_path, temp_path):
        path.mkdir(parents=True, exist_ok=True)
    return input_path, output_path, temp_path


def open_folder(folder_path: str) -> None:
    """Открывает папку в проводнике."""
    if not folder_path:
        return
    
    try:
        folder_path = str(Path(folder_path).resolve())
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{folder_path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
    except Exception as e:
        error_msg = f"Ошибка открытия папки: {e}"
        log_error(error_msg)
        raise RuntimeError(error_msg)


def log_error(error_msg: str, url: str = None) -> None:
    """Централизованное логирование ошибок."""
    log_dir = Path(__file__).parent.parent / 'data'
    log_file = log_dir / 'download_errors.log'
    
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            url_info = f" URL: {url}" if url else ""
            f.write(f"[{timestamp}]{url_info} {error_msg}\n")
    except Exception as e:
        print(f"Ошибка логирования: {e}")


@lru_cache(maxsize=100)
def extract_video_id(url: str) -> Optional[str]:
    """Извлекает ID видео из URL YouTube. Результаты кэшируются."""
    if not url:
        return None
        
    # Проверяем различные форматы YouTube URL
    youtube_patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/user\/.+\/watch\?v=)([^&\n?#]+)',
        r'youtube\.com\/shorts\/([^&\n?#]+)'
    ]
    
    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


class VideoInfoFetcher(QThread):
    """Поток для получения информации о видео."""
    info_ready = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._abort = False
        
    def abort(self) -> None:
        """Отменяет получение информации."""
        self._abort = True
        
    def run(self) -> None:
        """Запускает получение информации."""
        try:
            if self._abort:
                return
                
            # Проверяем, является ли URL ссылкой на YouTube
            video_id = extract_video_id(self.url)
            
            if video_id:
                # Для YouTube используем быстрый метод через API
                info = self._get_youtube_info(video_id)
            else:
                # Для других платформ используем yt_dlp с оптимизациями
                info = self._get_info_via_ytdlp()
                
            if self._abort:
                return
                
            self.info_ready.emit(info)
        except Exception as e:
            error_msg = f"Ошибка получения информации: {str(e)}"
            log_error(error_msg, self.url)
            self.error.emit(error_msg)
    
    def _get_youtube_info(self, video_id: str) -> Dict:
        """Получает информацию о видео YouTube через API."""
        # Используем oEmbed API для получения базовой информации о видео
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        
        try:
            with urllib.request.urlopen(oembed_url, timeout=3) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            # Создаем информационный объект
            info = {
                'title': data.get('title', 'Без названия'),
                'uploader': data.get('author_name', 'Неизвестно'),
                'thumbnail': f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",  # Прямой URL к миниатюре
                'id': video_id
            }
            return info
        except Exception:
            # Если API не сработал, пробуем через yt_dlp
            return self._get_info_via_ytdlp()
    
    def _get_info_via_ytdlp(self) -> Dict:
        """Получает информацию о видео через yt_dlp."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'skip_download': True,
            'writeinfojson': False,
            'writedescription': False,
            'writesubtitles': False,
            'writeannotations': False,
            'writethumbnail': False,
            'write_all_thumbnails': False,
            'simulate': True,
            'extract_flat': True,
            'socket_timeout': 5,  # Ограничиваем время ожидания
            'nocheckcertificate': True,  # Ускоряем загрузку
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=False, process=False)
            
            # Создаем упрощенный объект
            simple_info = {
                'title': info.get('title', 'Без названия'),
                'uploader': info.get('uploader', 'Неизвестно'),
                'thumbnail': info.get('thumbnail'),
                'id': info.get('id', '')
            }
            
            return simple_info


class VideoDownloader(QThread):
    """Поток скачивания видео."""
    update_progress = pyqtSignal(int)
    update_status = pyqtSignal(str)
    finished_with_error = pyqtSignal(str)
    download_complete = pyqtSignal()
    
    def __init__(self, url: str, save_path: str, format_id: str = None, log_file: str = None):
        super().__init__()
        self.url = url
        self.save_path = Path(save_path)
        self.format_id = format_id
        self.log_file = log_file or Path(__file__).parent.parent / 'data' / 'download_errors.log'
        self._abort = False
        self._downloaded_filepath: Optional[str] = None
        self._error: Optional[str] = None
        self._progress_throttle_counter = 0
        self._progress_throttle_limit = 10  # Обновлять UI каждые N обновлений

    def abort(self) -> None:
        """Отменяет скачивание."""
        self._abort = True

    def ydl_hook(self, d: Dict[str, Any]) -> None:
        """Обработчик событий скачивания. Использует троттлинг для обновления UI."""
        if self._abort:
            raise Exception("Загрузка отменена пользователем")
            
        status = d.get('status')
        if status == 'downloading':
            total = d.get('_total_bytes_estimate') or d.get('total_bytes') or 0
            downloaded = d.get('downloaded_bytes', 0)
            
            if total > 0:
                percent = min(int(downloaded * 100 / total), 100)
            else:
                percent = 0
                
            # Применяем троттлинг для обновлений UI
            self._progress_throttle_counter += 1
            if self._progress_throttle_counter >= self._progress_throttle_limit or percent >= 99:
                self.update_progress.emit(percent)
                self.update_status.emit(DownloadStatus.DOWNLOADING.value)
                self._progress_throttle_counter = 0
                
        elif status == 'finished':
            # Обновляем прогресс до 99%, так как процесс еще не полностью завершен
            self.update_progress.emit(99)
            self.update_status.emit(DownloadStatus.DOWNLOADING.value)

    def run(self) -> None:
        """Запускает скачивание."""
        try:
            if not self.save_path.exists():
                self.save_path.mkdir(parents=True, exist_ok=True)
                
            # Генерируем уникальное имя файла
            i = 1
            while any((self.save_path / f"video{i}.{ext}").exists() for ext in VIDEO_EXTS):
                i += 1
                
            outtmpl = str(self.save_path / f"video{i}.%(ext)s")
            
            ydl_opts = {
                'outtmpl': outtmpl,
                'format': self.format_id if self.format_id else 'bestvideo+bestaudio/best',
                'progress_hooks': [self.ydl_hook],
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'socket_timeout': 10,  # Увеличиваем время ожидания для скачивания
                'nocheckcertificate': True,  # Ускоряем скачивание
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
                
            # Проверяем, что файл скачался
            for ext in VIDEO_EXTS:
                candidate = self.save_path / f"video{i}.{ext}"
                if candidate.exists() and candidate.stat().st_size > 0:
                    self._downloaded_filepath = str(candidate)
                    break
                    
            if not self._downloaded_filepath:
                raise Exception("Файл не был скачан или пустой!")
                
            # Устанавливаем прогресс в 100% только в самом конце
            self.update_progress.emit(100)
            self.update_status.emit(DownloadStatus.FINISHED.value)
            self.download_complete.emit()
                
        except Exception as e:
            # Логируем ошибку
            log_error(f"Ошибка при скачивании: {e}", self.url)
            self._error = str(e)
            self.finished_with_error.emit(DownloadStatus.ERROR.value.format(error=e))
        finally:
            self._abort = False 