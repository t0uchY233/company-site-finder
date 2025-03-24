import os
import csv
import time
import pandas as pd
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
import streamlit as st
from urllib.parse import quote, urlparse
import random

# Импорт с поддержкой запуска и как модуля, и как скрипта
try:
    # При запуске как часть пакета
    from .utils.helpers import is_valid_website, clean_url, random_delay, format_search_query
except ImportError:
    # При запуске как скрипт
    from utils.helpers import is_valid_website, clean_url, random_delay, format_search_query

class CompanySiteFinder:
    def __init__(self, input_file=None, output_file=None, search_engine="google", headless=True, proxy=None):
        """
        Инициализация класса для поиска сайтов компаний
        :param input_file: Путь к входному CSV-файлу
        :param output_file: Путь к выходному CSV-файлу
        :param search_engine: Поисковая система ('google' или 'yandex')
        :param headless: Запускать браузер в фоновом режиме
        :param proxy: Прокси-сервер (опционально)
        """
        self.input_file = input_file
        self.output_file = output_file
        self.search_engine = search_engine.lower()
        self.headless = headless
        self.proxy = proxy
        self.driver = None
        self.results = {}
        
        if self.search_engine not in ["google", "yandex"]:
            raise ValueError("Поддерживаемые поисковые системы: 'google' или 'yandex'")
    
    def setup_driver(self):
        """Настройка драйвера Selenium"""
        try:
            # Настраиваем опции Chrome
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless=new")
            
            # Блокируем уведомления
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # Опции для снижения вероятности обнаружения автоматизации
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # Устанавливаем User-Agent как у обычного пользователя
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
            chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            # Устанавливаем язык
            chrome_options.add_argument("--lang=ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7")
            
            # Устанавливаем параметры окна
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Настраиваем прокси, если он указан
            if self.proxy:
                chrome_options.add_argument(f'--proxy-server={self.proxy}')
            
            # Инициализируем драйвер
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Устанавливаем размер окна
            self.driver.set_window_size(1920, 1080)
            
            # Устанавливаем параметры для скрытия автоматизации
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    window.chrome = {
                        runtime: {}
                    };
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """
            })
            
            # Устанавливаем таймаут по умолчанию для ожидания элементов
            self.driver.implicitly_wait(10)
            
            return self.driver
        
        except Exception as e:
            print(f"Ошибка при настройке драйвера: {e}")
            # Если драйвер был создан, закрываем его
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
            raise
    
    def load_companies(self):
        """Загрузка списка компаний из CSV-файла"""
        try:
            df = pd.read_csv(self.input_file)
            
            # Проверка наличия столбца с названиями компаний
            if 'Company Name' in df.columns:
                company_column = 'Company Name'
            elif 'CompanyName' in df.columns:
                company_column = 'CompanyName'
            elif 'company_name' in df.columns:
                company_column = 'company_name'
            elif 'Название' in df.columns:
                company_column = 'Название'
            elif 'название' in df.columns:
                company_column = 'название'
            elif 'Компания' in df.columns:
                company_column = 'Компания'
            elif 'компания' in df.columns:
                company_column = 'компания'
            else:
                # Если нет подходящего столбца, берем первый столбец
                company_column = df.columns[0]
            
            # Получаем список компаний
            companies = df[company_column].tolist()
            
            # Удаляем дубликаты и пустые значения
            companies = [str(company).strip() for company in companies if company and not pd.isna(company)]
            companies = list(set(companies))
            
            return companies
        except Exception as e:
            print(f"Ошибка при загрузке файла: {e}")
            return []
    
    def search_google(self, company_name):
        """Поиск сайта компании через Google"""
        try:
            # Формируем поисковый запрос
            query = format_search_query(company_name) + " официальный сайт"
            
            # Открываем Google
            self.driver.get("https://www.google.com/")
            
            # Принимаем все cookies, если есть такое окно
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Принимаю')]"))
                ).click()
                random_delay(1, 2)
            except:
                pass
            
            # Ищем поле ввода и вводим запрос
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)
            
            # Ждем загрузки результатов
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "search"))
            )
            
            # Получаем HTML-код страницы с результатами
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')
            
            # Извлекаем все ссылки из результатов поиска с разными селекторами для современной версии Google
            found_links = []
            
            # Пробуем различные селекторы для разных версий Google
            selectors = [
                'div.g div.yuRUbf a',                # Старый формат
                'div.g h3.LC20lb + div a',           # Альтернативный формат
                'div.tF2Cxc a',                      # Новый формат 2023
                'div.yuRUbf > a',                    # Еще один формат
                '.g .DhN8Cf a',                      # Обновленный Google 2024
                '.g .kvH3mc a',                      # Дополнительный селектор 2024
                'h3.LC20lb'                          # Поиск по заголовкам
            ]
            
            for selector in selectors:
                try:
                    elements = soup.select(selector)
                    if elements:
                        for element in elements:
                            # Извлекаем URL из атрибута href
                            href = None
                            if element.name == 'a':
                                href = element.get('href')
                            elif element.parent and element.parent.name == 'a':
                                href = element.parent.get('href')
                            elif element.find_parent('a'):
                                href = element.find_parent('a').get('href')
                                
                            if href and is_valid_website(href):
                                found_links.append(href)
                except Exception as e:
                    print(f"Ошибка при парсинге селектора {selector}: {e}")
            
            # Если ничего не нашли с помощью селекторов, берем все ссылки на странице
            if not found_links:
                all_links = soup.select('a[href^="http"]')
                
                for link in all_links:
                    href = link.get('href')
                    if href and is_valid_website(href):
                        found_links.append(href)
            
            # Фильтруем ссылки, исключая поисковые системы, соцсети и другие нерелевантные домены
            filtered_links = []
            for link in found_links:
                # Очищаем ссылку от UTM-меток и других параметров
                clean_link = clean_url(link)
                
                # Проверяем, не принадлежит ли ссылка к известным нерелевантным доменам
                non_relevant_domains = [
                    'google.com', 'yandex.ru', 'youtube.com', 'facebook.com', 'vk.com',
                    'instagram.com', 'twitter.com', 'linkedin.com', 'pinterest.com',
                    'wikipedia.org', 'wildberries.ru', 'ozon.ru', 'avito.ru', 'amazon.com',
                    'aliexpress.com', 'youla.ru', 'dzen.ru', 'rbc.ru', 'ria.ru',
                    'tass.ru', 'kommersant.ru', 'interfax.ru', 'lenta.ru'
                ]
                
                is_relevant = True
                for domain in non_relevant_domains:
                    if domain in clean_link.lower():
                        is_relevant = False
                        break
                
                if is_relevant:
                    filtered_links.append(clean_link)
            
            # Если нашли релевантные ссылки, возвращаем первую
            if filtered_links:
                return filtered_links[0]
            
            return None
        except Exception as e:
            print(f"Ошибка при поиске в Google для компании '{company_name}': {e}")
            return None
    
    def search_yandex(self, company_name):
        """Поиск сайта компании через Yandex с улучшенной механикой"""
        try:
            # Формируем поисковый запрос
            query = format_search_query(company_name)
            encoded_query = quote(query)
            
            # Используем прямую ссылку на поиск Яндекса с запросом
            search_url = f"https://yandex.ru/search/?text={encoded_query}"
            print(f"Открываем URL: {search_url}")
            
            # Открываем страницу поиска
            self.driver.get(search_url)
            
            # Пауза для имитации человеческого поведения
            random_delay(2, 4)
            
            # Принимаем все cookies, если есть такое окно
            try:
                cookies_buttons = self.driver.find_elements(By.XPATH, 
                    "//button[contains(., 'Принять') or contains(., 'Accept') or contains(., 'Да') or contains(., 'Yes')]")
                if cookies_buttons:
                    cookies_buttons[0].click()
                    random_delay(1, 2)
            except Exception as e:
                print(f"Не удалось обработать окно cookies: {e}")
                pass
            
            # Ждем загрузки результатов поиска с увеличенным таймаутом
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".serp-item, .OrganicTitle-Link, .organic, .serp-list"))
                )
                
                # Добавляем дополнительную паузу для полной загрузки страницы
                random_delay(2, 3)
                
                # Сделаем скролл вниз для загрузки всех результатов
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                random_delay(1, 2)
                
            except Exception as e:
                print(f"Ошибка при ожидании загрузки результатов Яндекса: {e}")
                
                # Попробуем продолжить даже если не дождались элементов
                random_delay(5, 7)
            
            # Получаем HTML-код страницы с результатами
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')
            
            # Список для хранения найденных ссылок
            found_links = []
            
            # Пробуем различные селекторы для извлечения ссылок из результатов поиска
            selectors = [
                # Новые селекторы для Яндекса (2024)
                'div.serp-item a.link[href^="http"]',
                'div.organic a.link[href^="http"]',
                'h2 a.OrganicTitle-Link',
                'div.Path a.link:not(.link_theme_outer)',
                '.Title a.link[href^="http"]',
                '.OrganicSearchSnippet a.OrganicSearchSnippet-LinkUrl',
                '.OrganicSnippet-LinkUrls a',
                '.organic a.link_outer, .organic a.OrganicTitle-Link',
                # Селекторы для разных версий Яндекса
                'a.OrganicTitle-Link, .OrganicSearchSnippet a',
                'a[href^="http"].link',
                '.organic__url',
                '.serp-url__link',
                '.typo_text_m a.link',
                # Осторожные селекторы для проверки наличия URL в тексте ссылки
                'a[href^="http"]:not([href*="yandex"]):not([href*="ya.ru"])'
            ]
            
            # Пробуем каждый селектор
            for selector in selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        href = element.get('href')
                        # Проверяем, что ссылка валидна и выглядит как сайт компании
                        if href and is_valid_website(href):
                            found_links.append(href)
                except Exception as e:
                    print(f"Ошибка при парсинге селектора {selector}: {e}")
            
            # Если ничего не нашли с помощью селекторов, берем все ссылки
            if not found_links:
                print("Не нашли ссылки по селекторам, пробуем найти все ссылки на странице")
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link.get('href')
                    # Проверка на http в начале ссылки и не из блэклиста
                    if href and href.startswith('http') and is_valid_website(href):
                        found_links.append(href)
            
            # Удаляем дубликаты
            found_links = list(dict.fromkeys(found_links))
            
            print(f"Найдено ссылок (до фильтрации): {len(found_links)}")
            
            # Фильтруем ссылки
            filtered_links = []
            blacklist_domains = [
                'yandex.ru', 'ya.ru', 'yandex.com', 'google.com', 'google.ru',
                'youtube.com', 'facebook.com', 'vk.com', 'instagram.com',
                'twitter.com', 'linkedin.com', 'pinterest.com', 'ok.ru',
                'wikipedia.org', 'fandom.com', 'wildberries.ru', 'ozon.ru',
                'avito.ru', 'youla.ru', 'dzen.ru', 'mail.ru', 'gosuslugi.ru',
                'rbc.ru', 'ria.ru', 'tass.ru', 'kommersant.ru', 'interfax.ru',
                'lenta.ru', 'gazeta.ru', 'vedomosti.ru', 'forbes.ru', 'kinopoisk.ru'
            ]
            
            for link in found_links:
                clean_link = clean_url(link)
                parsed_url = urlparse(link)
                domain = parsed_url.netloc.lower()
                
                # Проверяем, что домен не в черном списке
                if not any(bd in domain for bd in blacklist_domains):
                    filtered_links.append(clean_link)
            
            print(f"Найдено ссылок (после фильтрации): {len(filtered_links)}")
            
            # Если нашли релевантные ссылки, возвращаем первую
            if filtered_links:
                # Добавляем протокол, если его нет
                result = filtered_links[0]
                if not result.startswith('http'):
                    result = 'https://' + result
                return result
            
            return None
        except Exception as e:
            print(f"Ошибка при поиске в Яндексе для компании '{company_name}': {e}")
            return None
    
    def search_duckduckgo(self, company_name):
        """Поиск сайта компании через DuckDuckGo"""
        try:
            # Формируем поисковый запрос
            query = format_search_query(company_name)
            encoded_query = quote(query)
            
            # Используем прямой URL для поиска
            search_url = f"https://duckduckgo.com/?q={encoded_query}&t=h_&ia=web"
            print(f"Открываем URL DuckDuckGo: {search_url}")
            
            # Открываем страницу поиска
            self.driver.get(search_url)
            
            # Пауза для загрузки страницы
            random_delay(3, 5)
            
            # Принимаем cookies если необходимо
            try:
                cookies_buttons = self.driver.find_elements(By.XPATH, 
                    "//button[contains(text(), 'Accept') or contains(text(), 'Принять') or contains(text(), 'I Agree')]")
                if cookies_buttons:
                    cookies_buttons[0].click()
                    random_delay(1, 2)
            except Exception as e:
                print(f"Не удалось обработать окно cookies на DuckDuckGo: {e}")
            
            # Ждем загрузки результатов
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".result, .result__a, .result__url"))
                )
                
                # Дополнительная пауза и скролл страницы
                random_delay(2, 4)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
                random_delay(1, 2)
                
            except Exception as e:
                print(f"Ошибка при ожидании загрузки результатов DuckDuckGo: {e}")
                random_delay(5, 7)
            
            # Получаем HTML страницы
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')
            
            # Ищем ссылки с разными селекторами
            found_links = []
            
            selectors = [
                '.result__a',                        # Основной селектор для ссылок
                '.result__url',                      # URL в результатах
                '.result__snippet a',                # Ссылки в сниппете
                '.result__title a',                  # Заголовки результатов
                '.result_content a',                 # Контент результатов
                'a[href^="http"]:not([href*="duckduckgo.com"])',  # Все внешние ссылки
                'a[data-testid="result-title-a"]',    # Новый формат 2024
                '.react-results a.eVNpHGjtxRBq_gLOfGDr'  # Еще один формат 2024
            ]
            
            for selector in selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        href = element.get('href')
                        if href and is_valid_website(href):
                            found_links.append(href)
                except Exception as e:
                    print(f"Ошибка при парсинге селектора {selector} на DuckDuckGo: {e}")
            
            # Если ничего не нашли, берем все ссылки
            if not found_links:
                print("Не нашли ссылки по селекторам, пробуем найти все ссылки на странице DuckDuckGo")
                all_links = soup.find_all('a', href=True)
                
                for link in all_links:
                    href = link.get('href')
                    if href and href.startswith('http') and is_valid_website(href):
                        found_links.append(href)
            
            # Удаляем дубликаты
            found_links = list(dict.fromkeys(found_links))
            
            print(f"Найдено ссылок на DuckDuckGo (до фильтрации): {len(found_links)}")
            
            # Фильтруем ссылки
            filtered_links = []
            blacklist_domains = [
                'duckduckgo.com', 'google.com', 'yandex.ru', 'ya.ru', 'bing.com',
                'youtube.com', 'facebook.com', 'vk.com', 'instagram.com',
                'twitter.com', 'linkedin.com', 'pinterest.com', 'ok.ru',
                'wikipedia.org', 'fandom.com', 'wildberries.ru', 'ozon.ru',
                'avito.ru', 'youla.ru', 'dzen.ru', 'mail.ru', 'gosuslugi.ru',
                'amazon.com', 'ebay.com', 'aliexpress.com'
            ]
            
            for link in found_links:
                clean_link = clean_url(link)
                parsed_url = urlparse(link)
                domain = parsed_url.netloc.lower()
                
                # Проверяем, что домен не в черном списке
                if not any(bd in domain for bd in blacklist_domains):
                    filtered_links.append(clean_link)
            
            print(f"Найдено ссылок на DuckDuckGo (после фильтрации): {len(filtered_links)}")
            
            # Возвращаем первую валидную ссылку
            if filtered_links:
                result = filtered_links[0]
                if not result.startswith('http'):
                    result = 'https://' + result
                return result
            
            return None
        except Exception as e:
            print(f"Ошибка при поиске в DuckDuckGo для компании '{company_name}': {e}")
            return None
    
    def search_website(self, company_name):
        """Поиск сайта компании в зависимости от выбранной поисковой системы"""
        if self.search_engine == "google":
            return self.search_google(company_name)
        elif self.search_engine == "duckduckgo":
            return self.search_duckduckgo(company_name)
        else:
            return self.search_yandex(company_name)
    
    def save_results(self):
        """Сохранение результатов в CSV-файл"""
        if not self.results:
            print("Нет результатов для сохранения.")
            return
        
        try:
            # Создаем DataFrame из результатов
            df = pd.DataFrame({
                'Company Name': list(self.results.keys()),
                'Website': list(self.results.values())
            })
            
            # Сохраняем в CSV
            df.to_csv(self.output_file, index=False, encoding='utf-8-sig')
            
            print(f"Результаты сохранены в файл: {self.output_file}")
            return self.output_file
        except Exception as e:
            print(f"Ошибка при сохранении результатов: {e}")
            return None

def main(input_file, output_file, search_engine="google", headless=True, proxy=None, search_params=None):
    """
    Основная функция для запуска процесса поиска сайтов
    
    :param input_file: Путь к входному CSV-файлу со списком компаний
    :param output_file: Путь к выходному CSV-файлу для сохранения результатов
    :param search_engine: Поисковая система ('google' или 'yandex')
    :param headless: Запускать браузер в фоновом режиме
    :param proxy: Прокси-сервер (опционально)
    :param search_params: Словарь с дополнительными параметрами поиска:
        - max_retries: Максимальное количество попыток поиска для каждой компании
        - delay_seconds: Задержка между запросами в секундах
        - add_keywords: Добавлять ли ключевые слова к запросу
        - thorough_search: Использовать ли расширенный поиск
    :return: Словарь с результатами поиска
    """
    try:
        # Используем session_state для обновления прогресса если запущены из Streamlit
        is_streamlit = 'streamlit' in sys.modules
        
        # Устанавливаем параметры поиска по умолчанию
        if search_params is None:
            search_params = {}
        
        max_retries = search_params.get('max_retries', 1)
        delay_seconds = search_params.get('delay_seconds', 3)
        add_keywords = search_params.get('add_keywords', True)
        thorough_search = search_params.get('thorough_search', True)
        
        # Инициализируем finder
        finder = CompanySiteFinder(
            input_file=input_file,
            output_file=output_file,
            search_engine=search_engine,
            headless=headless,
            proxy=proxy
        )
        
        # Загружаем компании
        companies = finder.load_companies()
        
        if not companies:
            print("Список компаний пуст. Проверьте входной файл.")
            if is_streamlit:
                st.error("Список компаний пуст. Проверьте входной файл.")
            return None
        
        # Настройка драйвера
        try:
            finder.setup_driver()
        except Exception as e:
            print(f"Ошибка при настройке драйвера: {e}")
            if is_streamlit:
                st.error(f"Ошибка при настройке драйвера: {e}")
            return None
        
        try:
            total_companies = len(companies)
            
            print(f"Начинаем поиск сайтов для {total_companies} компаний...")
            print(f"Настройки поиска: max_retries={max_retries}, delay_seconds={delay_seconds}, add_keywords={add_keywords}, thorough_search={thorough_search}")
            
            for index, company in enumerate(companies):
                # Вычисляем прогресс
                progress = (index + 1) / total_companies
                progress_percent = progress * 100
                
                # Выводим статус в консоль
                print(f"Обработка {index + 1}/{total_companies} ({progress_percent:.1f}%): {company}")
                
                # Обновляем прогресс в Streamlit
                if is_streamlit:
                    st.session_state.progress = progress
                    st.session_state.status = f"Обработка {index + 1}/{total_companies} ({progress_percent:.1f}%): {company}"
                
                # Поиск сайта с несколькими попытками
                website = None
                attempt = 0
                
                while website is None and attempt < max_retries:
                    attempt += 1
                    if attempt > 1:
                        print(f"Повторная попытка поиска ({attempt}/{max_retries}) для: {company}")
                        if is_streamlit:
                            st.session_state.status = f"Повторная попытка {attempt}/{max_retries} для: {company}"
                    
                    # Поиск сайта
                    website = finder.search_website(company)
                    
                    # Пауза между попытками
                    if website is None and attempt < max_retries:
                        random_delay(delay_seconds, delay_seconds + 2)
                
                if website:
                    cleaned_url = clean_url(website)
                    print(f"Найден сайт: {cleaned_url}")
                    
                    # Добавляем протокол обратно для сохранения, если его нет
                    if not cleaned_url.startswith('http'):
                        cleaned_url = 'https://' + cleaned_url
                        
                    finder.results[company] = cleaned_url
                else:
                    print(f"Сайт не найден")
                    finder.results[company] = "Не найден"
                
                # Делаем паузу между запросами
                if index < total_companies - 1:  # Не ждем после последней компании
                    random_delay(delay_seconds, delay_seconds + 2)
            
            # Сохраняем результаты
            finder.save_results()
            
            print(f"Поиск завершен. Найдено {len([v for v in finder.results.values() if v != 'Не найден'])} сайтов из {total_companies}.")
            
            return finder.results
        
        except Exception as e:
            print(f"Ошибка при обработке компаний: {e}")
            if is_streamlit:
                st.error(f"Ошибка при обработке компаний: {e}")
            return None
        
        finally:
            # Закрываем драйвер
            if finder.driver:
                try:
                    finder.driver.quit()
                except:
                    pass
    
    except Exception as e:
        print(f"Ошибка в основной функции: {e}")
        if 'streamlit' in sys.modules:
            st.error(f"Ошибка в основной функции: {e}")
        return None

if __name__ == "__main__":
    # Пример использования скрипта напрямую
    input_file = "data/input/companies.csv"
    output_file = "data/output/results.csv"
    
    main(input_file, output_file) 