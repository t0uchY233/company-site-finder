import os
import sys
import time
import pandas as pd
import tempfile
import streamlit as st
from datetime import datetime
from io import StringIO
import traceback
import subprocess

# Добавляем текущую директорию в путь импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импортируем наш модуль scraper
try:
    from company_site_finder.scraper import main as scraper_main
except ImportError:
    from scraper import main as scraper_main

# Настройка конфигурации Streamlit
st.set_page_config(
    page_title="Поиск сайтов компаний",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Инициализация состояний сеанса для отслеживания прогресса
if 'progress' not in st.session_state:
    st.session_state.progress = 0.0
if 'status' not in st.session_state:
    st.session_state.status = "Готов к запуску"
if 'search_running' not in st.session_state:
    st.session_state.search_running = False
if 'total_companies' not in st.session_state:
    st.session_state.total_companies = 0
if 'results' not in st.session_state:
    st.session_state.results = None
if 'output_file' not in st.session_state:
    st.session_state.output_file = None

# Функция для проверки CSV-файла
def validate_csv(file):
    """
    Проверяет загруженный CSV-файл и возвращает результат
    :param file: Загруженный файл
    :return: (is_valid, result) - Флаг валидности и результат
    """
    try:
        # Читаем CSV-файл
        df = pd.read_csv(file)
        
        # Проверяем содержимое файла
        if df.empty:
            return False, "Файл не содержит данных"
        
        # Проверяем наличие нужных колонок
        valid_columns = ['Company Name', 'company name', 'company_name', 'name', 'Name', 'Название', 'название', 'Компания', 'компания']
        
        if not any(col in df.columns for col in valid_columns):
            # Если нет известных колонок, пробуем взять первую колонку
            if len(df.columns) > 0:
                first_col = df.columns[0]
                # Пробуем переименовать первую колонку
                df = df.rename(columns={first_col: 'Company Name'})
                return True, df
            else:
                return False, "В файле нет корректных колонок с названиями компаний"
        
        # Если нашли подходящую колонку, переименуем ее для стандартизации
        for col in valid_columns:
            if col in df.columns:
                df = df.rename(columns={col: 'Company Name'})
                break
        
        # Проверяем наличие непустых значений
        if df['Company Name'].isnull().all():
            return False, "Колонка с названиями компаний пуста"
        
        # Удаляем пустые строки
        df = df.dropna(subset=['Company Name'])
        
        # Удаляем дубликаты
        df = df.drop_duplicates(subset=['Company Name'])
        
        return True, df
    
    except Exception as e:
        return False, f"Ошибка при чтении файла: {e}"

# Функция для сохранения загруженного файла
def save_uploaded_file(uploaded_file):
    """
    Сохраняет загруженный файл во временную директорию
    :param uploaded_file: Загруженный файл
    :return: (success, path) - Флаг успеха и путь к сохраненному файлу
    """
    try:
        os.makedirs('data/input', exist_ok=True)
        
        # Создаем имя файла на основе времени
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"input_{timestamp}.csv"
        file_path = os.path.join('data/input', file_name)
        
        # Сохраняем файл
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return True, file_path
    
    except Exception as e:
        return False, f"Ошибка при сохранении файла: {e}"

def setup_settings():
    """Настройка боковой панели с настройками"""
    with st.sidebar:
        st.header("Настройки")
        
        # Выбор поисковой системы
        search_engine = st.selectbox(
            "Поисковая система",
            options=["google", "yandex", "duckduckgo"],
            index=1,  # Яндекс по умолчанию, так как он более стабилен
            help="Выберите поисковую систему для поиска сайтов компаний. Яндекс обычно более стабилен для поиска российских компаний."
        )
        
        # Режим запуска браузера
        headless = st.checkbox(
            "Фоновый режим",
            value=True,
            help="Если включено, браузер будет работать в фоновом режиме без отображения окна. Отключите для отладки."
        )
        
        # Настройки поиска
        st.subheader("Настройки поиска")
        
        delay_seconds = st.slider(
            "Задержка между запросами (сек)",
            min_value=3,
            max_value=15,
            value=5,
            step=1,
            help="Задержка между поисковыми запросами для снижения вероятности блокировки со стороны поисковых систем."
        )
        
        max_retries = st.slider(
            "Макс. количество попыток",
            min_value=1,
            max_value=5,
            value=2,
            step=1,
            help="Максимальное количество попыток поиска для каждой компании в случае неудачи."
        )
        
        # Расширенные настройки
        with st.expander("Расширенные настройки", expanded=False):
            add_keywords = st.checkbox(
                "Добавлять ключевые слова",
                value=True,
                help="Добавлять ключевые слова к запросу для улучшения результатов (например, 'официальный сайт')."
            )
            
            thorough_search = st.checkbox(
                "Расширенный поиск",
                value=True,
                help="Использовать дополнительные методы поиска для повышения точности результатов."
            )
            
            proxy = st.text_input(
                "Прокси-сервер (опционально)",
                value="",
                help="Укажите адрес прокси-сервера в формате 'ip:port' или 'user:pass@ip:port'."
            )
        
        # Создаем словарь с настройками
        settings = {
            "search_engine": search_engine,
            "headless": headless,
            "proxy": proxy if proxy else None,
            "search_params": {
                "max_retries": max_retries,
                "delay_seconds": delay_seconds,
                "add_keywords": add_keywords,
                "thorough_search": thorough_search
            }
        }
        
        return settings

def display_search_tips():
    """Отображает рекомендации по поиску"""
    with st.expander("Советы по улучшению поиска", expanded=False):
        st.markdown("""
        ### Рекомендации по использованию:
        
        **Выбор поисковой системы:**
        - **Яндекс** - лучше работает для российских компаний, но может чаще блокировать автоматизированные запросы.
        - **Google** - имеет широкий охват, но часто блокирует автоматизированные запросы.
        - **DuckDuckGo** - менее склонен к блокировке, но может давать менее точные результаты для российских компаний.
        
        **Оптимизация запросов:**
        - Используйте полные названия компаний с юридической формой (например, "ООО Компания" вместо просто "Компания").
        - Для компаний с общими названиями добавляйте регион или сферу деятельности (например, "Строй Москва" вместо просто "Строй").
        - При высокой вероятности блокировки увеличьте задержку между запросами до 7-10 секунд.
        
        **Использование прокси:**
        - Используйте ротацию прокси для предотвращения блокировки.
        - Рекомендуется использовать IP-адреса из России для лучших результатов поиска российских компаний.
        
        **В случае блокировки:**
        - Попробуйте отключить фоновый режим и использовать другую поисковую систему.
        - Увеличьте задержку между запросами.
        - Используйте надежные прокси-серверы.
        """)

def main():
    """Основная функция приложения"""
    # Заголовок приложения
    st.title("Поиск сайтов компаний 🔎")
    
    # Информация о приложении
    with st.expander("О приложении", expanded=False):
        st.info("""
        Это приложение автоматически ищет официальные сайты компаний по их названиям.
        
        Просто загрузите CSV-файл со списком названий компаний, и приложение найдет их официальные сайты, используя поисковые системы.
        
        **Как использовать:**
        1. Загрузите CSV-файл со списком компаний
        2. Выберите настройки поиска
        3. Нажмите кнопку "Начать поиск"
        4. Дождитесь завершения и скачайте результаты
        """)
    
    # Получаем настройки из боковой панели
    settings = setup_settings()
    
    # Отображаем рекомендации по поиску
    display_search_tips()
    
    # Переключатель для способа ввода данных
    input_method = st.radio(
        "Способ ввода данных",
        ["Загрузить CSV-файл", "Ввести названия компаний вручную"],
        horizontal=True
    )
    
    # Переменные для хранения данных
    df = None
    input_file_path = None
    
    if input_method == "Загрузить CSV-файл":
        # Загрузка файла
        uploaded_file = st.file_uploader("Загрузите CSV-файл со списком компаний", type=["csv"])
        
        if uploaded_file is not None:
            # Проверяем файл
            is_valid, result = validate_csv(uploaded_file)
            
            if is_valid:
                df = result
                
                # Показываем предпросмотр данных
                st.subheader("Предпросмотр данных")
                st.dataframe(df.head(5), use_container_width=True)
                
                # Сохраняем загруженный файл
                saved, input_file_path = save_uploaded_file(uploaded_file)
                
                if not saved:
                    st.error(input_file_path)
                    input_file_path = None
            else:
                st.error(f"Ошибка при проверке файла: {result}")
    else:
        # Ручной ввод списка компаний
        manual_input = st.text_area(
            "Введите названия компаний (по одной на строку)",
            height=150,
            help="Введите название каждой компании на отдельной строке"
        )
        
        if manual_input:
            companies = [company.strip() for company in manual_input.split('\n') if company.strip()]
            
            if companies:
                # Создаем DataFrame из списка
                df = pd.DataFrame({"Company Name": companies})
                
                # Показываем предпросмотр данных
                st.subheader("Предпросмотр данных")
                st.dataframe(df.head(5), use_container_width=True)
                
                # Временное сохранение в файл
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                os.makedirs("data/input", exist_ok=True)
                input_file_path = f"data/input/manual_input_{timestamp}.csv"
                df.to_csv(input_file_path, index=False)
            else:
                st.warning("Пожалуйста, введите хотя бы одно название компании.")
    
    # Если у нас есть данные и путь к файлу, показываем кнопку начала поиска
    if df is not None and input_file_path is not None:
        # Создаем путь для выходного файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_dir = "data/output"
        os.makedirs(output_file_dir, exist_ok=True)
        output_file_path = f"{output_file_dir}/results_{timestamp}.csv"
        
        # Кнопка для запуска процесса поиска
        start_search = st.button("Начать поиск", type="primary", disabled=st.session_state.search_running)
        
        # Блок с прогрессом
        progress_placeholder = st.empty()
        
        if start_search or st.session_state.search_running:
            st.session_state.search_running = True
            
            with progress_placeholder.container():
                st.subheader("Выполняется поиск сайтов...")
                progress_bar = st.progress(0.0)
                
                # Обновляем прогресс-бар
                progress_bar.progress(st.session_state.progress)
                
                # Показываем текущий статус
                status_text = st.empty()
                status_text.text(st.session_state.status)
                
                # Запускаем поиск, если он еще не запущен
                if st.session_state.results is None:
                    try:
                        # Запускаем процесс поиска
                        result = scraper_main(
                            input_file=input_file_path,
                            output_file=output_file_path,
                            search_engine=settings["search_engine"],
                            headless=settings["headless"],
                            proxy=settings["proxy"],
                            search_params=settings["search_params"]
                        )
                        
                        # Сохраняем результаты в состояние сессии
                        st.session_state.results = result
                        st.session_state.output_file = output_file_path
                        st.session_state.search_running = False
                        st.session_state.progress = 1.0
                        st.session_state.status = "Поиск завершен!"
                        
                        # Перезагружаем страницу для обновления интерфейса
                        st.rerun()
                    except Exception as e:
                        st.error(f"Произошла ошибка при поиске: {e}")
                        st.code(traceback.format_exc())
                        st.session_state.search_running = False
                        
                else:
                    # Обновляем прогресс-бар до 100%
                    progress_bar.progress(1.0)
                    
                    # Показываем результаты
                    st.success("Поиск успешно завершен!")
                    
                    # Показываем результаты в виде таблицы
                    if st.session_state.results:
                        result_df = pd.DataFrame({
                            'Компания': list(st.session_state.results.keys()),
                            'Сайт': list(st.session_state.results.values())
                        })
                        
                        st.subheader("Результаты поиска:")
                        st.dataframe(result_df, use_container_width=True)
                        
                        # Статистика по найденным сайтам
                        found_count = len([v for v in st.session_state.results.values() if v != "Не найден"])
                        total_count = len(st.session_state.results)
                        found_percent = (found_count / total_count) * 100 if total_count > 0 else 0
                        
                        st.info(f"Найдено {found_count} сайтов из {total_count} компаний ({found_percent:.1f}%)")
                        
                        # Кнопка для скачивания результатов
                        if st.session_state.output_file and os.path.exists(st.session_state.output_file):
                            with open(st.session_state.output_file, "rb") as file:
                                btn = st.download_button(
                                    label="Скачать результаты в CSV",
                                    data=file,
                                    file_name=f"company_sites_{timestamp}.csv",
                                    mime="text/csv"
                                )
                        
                        # Кнопка для нового поиска
                        if st.button("Начать новый поиск"):
                            # Сбрасываем состояние
                            st.session_state.results = None
                            st.session_state.output_file = None
                            st.session_state.search_running = False
                            st.session_state.progress = 0.0
                            st.session_state.status = "Готов к запуску"
                            st.rerun()
    
    # Футер
    st.markdown("---")
    st.caption("© 2024 Company Site Finder | Версия 0.2.0")

if __name__ == "__main__":
    main() 