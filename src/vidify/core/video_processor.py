"""
Модуль для обработки видео с помощью FFmpeg.
"""
import os
import subprocess
import time
from threading import Event
from typing import List, Optional, Tuple
from PyQt5.QtCore import QThread, pyqtSignal


class FFmpegProcessor(QThread):
    """Класс для асинхронного выполнения команд FFmpeg."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, cmd: List[str], output_path: Optional[str] = None, parse_progress: bool = False, total_frames: Optional[int] = None):
        super().__init__()
        self.cmd = cmd
        self.output_path = output_path
        self.parse_progress = parse_progress
        self.total_frames = total_frames
        self.process = None
        self.stop_event = Event()

    def run(self) -> None:
        """Запускает выполнение команды FFmpeg."""
        try:
            if self.parse_progress:
                try:
                    # Сначала получаем общее количество фреймов для расчета процентов
                    if not self.total_frames:
                        duration_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                                      '-show_entries', 'stream=nb_frames', 
                                      '-of', 'default=noprint_wrappers=1:nokey=1', 
                                      self.cmd[self.cmd.index('-i')+1]]
                        try:
                            result = subprocess.check_output(duration_cmd, stderr=subprocess.STDOUT)
                            self.total_frames = int(result.decode('utf-8').strip()) or 1000
                        except:
                            self.total_frames = 1000  # Значение по умолчанию
                    self.process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                                  universal_newlines=True, bufsize=1)
                    stderr_lines = []
                    for line in iter(self.process.stderr.readline, ''):
                        if self.stop_event.is_set():
                            self.process.terminate()
                            break
                        stderr_lines.append(line)
                        if 'frame=' in line:
                            try:
                                frame_parts = line.split('frame=')[1].strip().split(' ')[0]
                                current_frame = int(frame_parts)
                                percent = min(int(current_frame * 100 / self.total_frames), 100)
                                self.progress.emit(percent)
                            except (ValueError, IndexError):
                                pass
                    if not self.stop_event.is_set():
                        exit_code = self.process.wait()
                        if exit_code == 0:
                            self.finished.emit(self.output_path or "OK")
                        else:
                            error_msg = f"FFmpeg завершился с ошибкой: код {exit_code}\n" + ''.join(stderr_lines)
                            self.error.emit(error_msg)
                except Exception as e:
                    self.error.emit(str(e))
            else:
                result = subprocess.run(self.cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.finished.emit(self.output_path or "OK")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode('utf-8') if hasattr(e.stderr, 'decode') else str(e.stderr)
            self.error.emit(f"FFmpeg ошибка: {e}\n{stderr}")
        except Exception as e:
            self.error.emit(str(e))

    def stop(self) -> None:
        """Останавливает выполнение FFmpeg."""
        if self.process:
            self.stop_event.set()


def create_ffmpeg_command(input_path: str, output_path: str, filter_str: Optional[str], is_preview: bool = False, frame_time: str = "00:00:00.2") -> List[str]:
    """Создает команду ffmpeg на основе параметров."""
    cmd = ['ffmpeg', '-y']
    
    # Для превью берем указанный кадр, по умолчанию 0.2 секунды
    if is_preview:
        cmd.extend(['-ss', frame_time, '-i', input_path])
    else:
        cmd.extend(['-i', input_path])
    
    # Если фильтр содержит overlay или именованные потоки — используем -filter_complex
    if filter_str and ("overlay" in filter_str or "[" in filter_str):
        cmd.extend(['-filter_complex', filter_str])
    elif filter_str:
        cmd.extend(['-vf', filter_str])
    else:
        # Если нет фильтров, оставляем видео без изменений
        pass
        
    # Для превью берем только один кадр
    if is_preview:
        cmd.extend(['-frames:v', '1', '-update', '1'])
    else:
        # При обработке полного видео копируем аудио дорожку, если она есть
        cmd.extend(['-c:a', 'copy'])
        
    cmd.append(output_path)
    return cmd


def check_ffmpeg_available() -> bool:
    """Проверяет доступность FFmpeg в системе."""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def cleanup_temp_files(temp_dir: str, max_age_hours: int = 1) -> None:
    """Очищает временные файлы старше указанного времени."""
    try:
        now = time.time()
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            # Если файл старше max_age_hours часов, удаляем его
            if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > max_age_hours * 3600:
                os.remove(file_path)
    except Exception as e:
        print(f"Ошибка при очистке временных файлов: {e}") 