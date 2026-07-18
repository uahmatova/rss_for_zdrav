import feedparser
import datetime
import requests
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup  # Новая библиотека для парсинга HTML

# --- НАСТРОЙКА: список твоих RSS-лент ---
RSS_SOURCES = [
    "https://permkrai.ru/news/rss.php",
    "https://v-kurse.ru/rss.xml",
    "https://zwezda.su/rss"
]

# --- ФУНКЦИЯ, которая пытается получить RSS или парсит HTML ---
def fetch_feed(url):
    print(f"Обработка: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        }
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Проверяем, что вернулось
        content_type = response.headers.get('Content-Type', '')
        
        # Если это HTML — парсим новости прямо из HTML
        if 'html' in content_type.lower():
            print("  Сервер вернул HTML, парсим новости напрямую...")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            items = []
            # Ищем элементы новостей на странице (подбирай селекторы под сайт)
            # Для permkrai.ru обычно новости в <article> или <div class="news-item">
            news_items = soup.find_all('article') or soup.find_all('div', class_='news-item') or soup.find_all('li', class_='news')
            
            if not news_items:
                # Если не нашлись, ищем любые ссылки с датами
                news_items = soup.find_all('a', href=True)
            
            for item in news_items[:20]:  # Берем не больше 20
                # Пытаемся найти заголовок
                title_elem = item.find('h2') or item.find('h3') or item.find('span', class_='title') or item
                title = title_elem.get_text(strip=True) if title_elem else "Новость"
                
                # Пытаемся найти ссылку
                link_elem = item if item.name == 'a' else item.find('a', href=True)
                if link_elem and link_elem.get('href'):
                    link = link_elem.get('href')
                    if not link.startswith('http'):
                        link = 'https://permkrai.ru' + link
                else:
                    link = url
                
                # Пытаемся найти описание
                desc_elem = item.find('p') or item.find('div', class_='description') or item
                description = desc_elem.get_text(strip=True)[:200] if desc_elem else ""
                
                # Пытаемся найти дату
                date_elem = item.find('time') or item.find('span', class_='date')
                pub_date = date_elem.get_text(strip=True) if date_elem else datetime.datetime.now().isoformat()
                
                items.append({
                    'title': title,
                    'link': link,
                    'description': description,
                    'pub_date': pub_date,
                    'source': url
                })
            
            print(f"  Спарсено {len(items)} новостей из HTML")
            return items
        
        # Если это RSS — парсим как обычно
        feed = feedparser.parse(response.content)
        if feed.bozo:
            print(f"  Ошибка парсинга RSS: {feed.bozo_exception}")
            return []
            
        items = []
        for entry in feed.entries:
            title = entry.get('title', 'Без заголовка')
            link = entry.get('link', '')
            description = entry.get('description', entry.get('summary', ''))
            pub_date = entry.get('published', entry.get('updated', ''))
            
            items.append({
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date,
                'source': url
            })
        print(f"  Загружено {len(items)} новостей из RSS")
        return items
        
    except Exception as e:
        print(f"  ОШИБКА при загрузке {url}: {e}")
        return []

# --- 1. Скачиваем все новости из всех источников ---
all_news = []
for rss_url in RSS_SOURCES:
    news_from_source = fetch_feed(rss_url)
    all_news.extend(news_from_source)

print(f"Всего собрано {len(all_news)} новостей.")

# --- 2. Сортируем по дате ---
def parse_date(date_string):
    if not date_string:
        return datetime.datetime(1970, 1, 1)
    try:
        return datetime.datetime.strptime(date_string, "%a, %d %b %Y %H:%M:%S %Z")
    except:
        try:
            return datetime.datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except:
            return datetime.datetime.now()

all_news.sort(key=lambda x: parse_date(x['pub_date']), reverse=True)

# --- 3. Создаем RSS-файл ---
rss_root = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss_root, "channel")

ET.SubElement(channel, "title").text = "Объединенная лента новостей Прикамья"
ET.SubElement(channel, "description").text = "Новости с permkrai.ru и v-kurse.ru"

for item in all_news:
    item_element = ET.SubElement(channel, "item")
    ET.SubElement(item_element, "title").text = item['title']
    ET.SubElement(item_element, "link").text = item['link']
    
    desc_element = ET.SubElement(item_element, "description")
    desc_element.text = f"<![CDATA[{item['description']}]]>"
    
    pub_element = ET.SubElement(item_element, "pubDate")
    pub_element.text = str(item['pub_date'])

tree = ET.ElementTree(rss_root)
tree.write('merged_feed.xml', encoding='utf-8', xml_declaration=True)

print(f"✅ RSS-лента создана с {len(all_news)} новостями!")
