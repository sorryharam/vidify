#!/usr/bin/env python3
"""
Скрипт для автоматической загрузки шрифта Monocraft.
Запустите этот скрипт, чтобы загрузить шрифт Monocraft из GitHub и поместить его в нужную директорию.
"""

import os
import sys
import requests
from pathlib import Path

# URL для загрузки шрифта Monocraft (последняя версия 4.0)
FONT_URL = "https://github.com/IdreesInc/Monocraft/releases/download/v4.0/Monocraft.ttc"

def main():
    """Основная функция для загрузки и установки шрифта."""
    print("Загрузка шрифта Monocraft версии 4.0...")
    
    # Определяем путь для сохранения шрифта
    script_dir = Path(__file__).parent
    font_path = script_dir / "Monocraft.ttc"
    
    try:
        # Загружаем шрифт
        print(f"Загрузка с URL: {FONT_URL}")
        response = requests.get(FONT_URL, timeout=15)
        response.raise_for_status()  # Проверяем на ошибки HTTP
        
        # Сохраняем файл
        with open(font_path, "wb") as f:
            f.write(response.content)
        
        print(f"Шрифт успешно загружен и сохранен в: {font_path}")
        print(f"Размер файла: {len(response.content) / 1024:.1f} KB")
        
        # Инструкции по установке
        print("\nДля завершения установки:")
        
        if sys.platform == "win32":
            print("1. Щелкните правой кнопкой мыши на файле шрифта и выберите 'Установить'")
        elif sys.platform == "darwin":
            print("1. Дважды щелкните на файле шрифта и нажмите 'Установить шрифт'")
        else:  # Linux
            print("1. Скопируйте файл шрифта в ~/.local/share/fonts/")
            print("2. Выполните команду 'fc-cache -fv' в терминале")
        
        print("3. Перезапустите приложение VIDIFY")
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке шрифта: {e}")
        print("Попробуйте скачать шрифт вручную: https://github.com/IdreesInc/Monocraft/releases/latest")
        sys.exit(1)
    except IOError as e:
        print(f"Ошибка при сохранении файла: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 