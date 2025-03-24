import random
import time
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def is_valid_website(url):
    """
    Проверяет, является ли URL валидным сайтом компании
    :param url: URL для проверки
    :return: True, если URL валиден, иначе False
    """
    try:
        # Базовая проверка URL
        if not url or not isinstance(url, str):
            return False
            
        # Проверка на пустую строку или слишком короткий URL
        if len(url.strip()) < 5:  # Минимальная длина URL (например, t.co)
            return False
            
        # Проверка на наличие протокола
        if not url.startswith('http://') and not url.startswith('https://'):
            # Иногда в результатах поиска встречаются URL без протокола
            if not re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}', url):
                return False
                
        # Парсим URL
        parsed_url = urlparse(url)
        
        # Проверка домена
        if not parsed_url.netloc:
            return False
            
        # Проверка на специальные символы в домене (кроме дефиса и точки)
        if re.search(r'[^a-zA-Z0-9.-]', parsed_url.netloc):
            # Исключаем международные домены, которые могут содержать специальные символы
            if not parsed_url.netloc.startswith('xn--'):
                return False
                
        # Проверка на минимальную длину домена
        parts = parsed_url.netloc.split('.')
        if len(parts) < 2 or any(len(part) < 1 for part in parts):
            return False
            
        # Проверка на валидное доменное имя верхнего уровня (TLD)
        tld = parts[-1].lower()
        valid_tlds = ['com', 'ru', 'org', 'net', 'edu', 'gov', 'io', 'co', 'info', 'biz', 
                      'рф', 'ua', 'uk', 'de', 'fr', 'es', 'it', 'cn', 'jp', 'kr', 'br',
                      'au', 'nz', 'ca', 'eu', 'me', 'tv', 'pro', 'online', 'store', 'shop',
                      'app', 'blog', 'dev', 'tech', 'site', 'web', 'club', 'xyz', 'agency',
                      'su', 'by', 'kz', 'am', 'az', 'ge', 'kg', 'md', 'tj', 'tm', 'uz',
                      'cymru', 'london', 'moscow', 'рус', 'tatar', '移动', '健康', '娱乐']
        
        # Поддержка всех распространенных TLD через проверку длины
        if tld not in valid_tlds and len(tld) > 5:
            return False
            
        return True
        
    except Exception as e:
        print(f"Ошибка при проверке URL {url}: {e}")
        return False

def clean_url(url):
    """
    Очищает URL от параметров отслеживания и других ненужных элементов
    :param url: URL для очистки
    :return: Очищенный URL
    """
    try:
        # Если URL не строка, возвращаем как есть
        if not url or not isinstance(url, str):
            return url
            
        # Убираем лишние пробелы
        url = url.strip()
        
        # Если URL не начинается с http/https, добавляем протокол
        if not url.startswith('http://') and not url.startswith('https://'):
            if not url.startswith('//'):
                url = 'https://' + url
            else:
                url = 'https:' + url
                
        # Парсим URL
        parsed_url = urlparse(url)
        
        # Получаем домен и путь
        netloc = parsed_url.netloc
        path = parsed_url.path
        
        # Фильтруем параметры запроса, удаляя параметры отслеживания
        tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                          'fbclid', 'gclid', 'yclid', 'dclid', 'zanpid', 'msclkid',
                          '_openstat', 'ysclid', 'mkt_tok', 'vero_id', 'ref', 'referrer',
                          'source', 'source_id', 'tracking', 'trackingid', 'sessionid',
                          '_ga', '_gl', '_bta_tid', '_bta_c', 'trk', 'mc_cid', 'mc_eid']
        
        # Если есть параметры запроса, фильтруем их
        if parsed_url.query:
            query_dict = parse_qs(parsed_url.query)
            filtered_query = {k: v for k, v in query_dict.items() if k.lower() not in tracking_params}
            
            # Преобразуем обратно в строку запроса
            query_string = urlencode(filtered_query, doseq=True) if filtered_query else ''
        else:
            query_string = ''
            
        # Убираем фрагмент URL (часть после #), если он есть
        fragment = ''
        
        # Собираем URL обратно
        clean_parsed = urlparse(url)
        clean_parsed = clean_parsed._replace(
            query=query_string,
            fragment=fragment
        )
        cleaned_url = urlunparse(clean_parsed)
        
        # Удаляем www. в начале домена, если есть
        if netloc.startswith('www.'):
            netloc = netloc[4:]
            cleaned_url = cleaned_url.replace('://www.', '://', 1)
            
        # Удаляем trailing slash в конце URL, если это корневой URL
        if path == '/' and not query_string and not fragment:
            cleaned_url = cleaned_url.rstrip('/')
            
        return cleaned_url
        
    except Exception as e:
        print(f"Ошибка при очистке URL {url}: {e}")
        return url

def random_delay(min_seconds=1, max_seconds=3):
    """
    Создает случайную задержку для имитации человеческого поведения
    :param min_seconds: Минимальное время задержки в секундах
    :param max_seconds: Максимальное время задержки в секундах
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def format_search_query(company_name):
    """
    Форматирует название компании для поискового запроса
    :param company_name: Название компании
    :return: Отформатированный запрос
    """
    # Удаляем лишние пробелы и приводим к нижнему регистру
    query = company_name.strip()
    
    # Обрабатываем кавычки - они могут мешать поиску
    query = query.replace('"', ' ').replace("'", ' ').replace("`", ' ')
    
    # Удаляем специальные символы, которые могут мешать поиску
    query = re.sub(r'[\\/%@#$^&*()_+=\[\]{}|<>~`]', ' ', query)
    
    # Заменяем множественные пробелы на один
    query = re.sub(r'\s+', ' ', query)
    
    return query

# Тестовый код для проверки функций
if __name__ == "__main__":
    test_companies = [
        "1 МСМУ Стальмонтаж",
        "1П Технолоджиз",
        "MAX",
        "Eвразия-Групп",
        "2Н ГРУПП",
        "247 СТРОЙ",
        "3 М ФАСАД",
        "2А-Инжиниринг",
        "KC",
    ]
    
    print("=== Тестирование форматирования запросов ===")
    for company in test_companies:
        formatted = format_search_query(company)
        print(f"'{company}' -> '{formatted}'")
    
    print("\n=== Тестирование очистки URL ===")
    test_urls = [
        "https://www.example.com",
        "http://example.com/path/to/page?utm_source=google",
        "https://www.company.ru/about/",
        "https://sub.domain.co.uk/products#section1",
        "http://www.xn--80aswg.xn--p1ai/",  # сайт.рф
    ]
    
    for url in test_urls:
        cleaned = clean_url(url)
        print(f"'{url}' -> '{cleaned}'")
    
    print("\n=== Тестирование валидации вебсайтов ===")
    for url in test_urls + ["https://google.com/search", "https://facebook.com/profile", "not_a_url", "www.example.com"]:
        is_valid = is_valid_website(url)
        print(f"'{url}' -> {'Валидный' if is_valid else 'Невалидный'}") 