#!/usr/bin/env python
"""
Скрипт для запуска приложения поиска сайтов компаний
"""
import os
import sys
import subprocess

def main():
    """
    Запуск приложения через Streamlit
    """
    # Определяем путь к текущей директории
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Проверяем наличие установленных зависимостей
    try:
        import streamlit
        import selenium
        import pandas
        import beautifulsoup4
    except ImportError:
        print("Установка необходимых зависимостей...")
        requirements_path = os.path.join(current_dir, "requirements.txt")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
    
    # Запускаем приложение
    app_path = os.path.join(current_dir, "app.py")
    print(f"Запуск приложения из {app_path}")
    subprocess.check_call([sys.executable, "-m", "streamlit", "run", app_path])

if __name__ == "__main__":
    main() 