pip install feedparser
pip install --user beautifulsoup4

import feedparser
import datetime
import requests
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
import re

# --- НАСТРОЙКА: список твоих RSS-лент ---
RSS_SOURCES = [
    "https://permkrai.ru/news/rss.php",
    "https://v-kurse.ru/rss.xml",
    "https://zwezda.su/rss"
]

# --- ФУНКЦИЯ ОЧИСТКИ ОПИСАНИЯ ---
def clean_description(text):
    if not text:
        return ""
    phrases_to_remove = [
        'Подписывайтесь на нас в Telegram',
        'Подписывайтесь на нас в Max',
        'Подписывайтесь на нас в Telegram и Max',
        'Подписывайтесь на нас в соцсетях',
        'Читайте нас в Telegram',
        'Подписывайтесь на нас в социальных сетях',
        'Подписывайся на нас в Telegram',
    ]
    for phrase in phrases_to_remove:
        text = text.replace(phrase, '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# --- ФУНКЦИЯ ИЗВЛЕЧЕНИЯ КАРТИНКИ ИЗ RSS ---
def extract_image(entry):
    if 'enclosures' in entry and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/'):
                return enc.get('href', '')
    if 'media_content' in entry:
        for media in entry.media_content:
            if media.get('type', '').startswith('image/'):
                return media.get('url', '')
    if 'description' in entry:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.description)
        if img_match:
            return img_match.group(1)
    return ''

# --- ФУНКЦИЯ ИЗВЛЕЧЕНИЯ КАРТИНКИ ИЗ HTML ---
def extract_image_html(item, base_url='https://permkrai.ru'):
    image_div = item.find('div', class_='image')
    if image_div and image_div.get('style'):
        style = image_div.get('style')
        img_match = re.search(r'url\(["\']?([^"\'()]+)["\']?\)', style)
        if img_match:
            img_url = img_match.group(1)
            if not img_url.startswith('http'):
                img_url = base_url + img_url
            return img_url
    
    img_tag = item.find('img')
    if img_tag and img_tag.get('src'):
        img_url = img_tag.get('src')
        if not img_url.startswith('http'):
            img_url = base_url + img_url
        return img_url
    
    if item.name == 'a':
        img_tag = item.find('img')
        if img_tag and img_tag.get('src'):
            img_url = img_tag.get('src')
            if not img_url.startswith('http'):
                img_url = base_url + img_url
            return img_url
    
    return ''

# --- ФУНКЦИЯ ЗАГРУЗКИ ЛЕНТЫ ---
def fetch_feed(url):
    print(f"Обработка: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        }

        session = requests.Session()
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')

        # --- HTML-ПАРСИНГ (для permkrai.ru) ---
        if 'html' in content_type.lower():
            print("  Сервер вернул HTML, парсим новости напрямую...")
            soup = BeautifulSoup(response.text, 'html.parser')

            items = []
            news_container = soup.find('div', class_='block news-container')
            if news_container:
                news_blocks = news_container.find_all('div', class_='col-lg-4')
            else:
                news_blocks = soup.find_all('div', class_='col-lg-4')

            if not news_blocks:
                news_blocks = soup.find_all('a', class_='news-item')

            print(f"  Найдено блоков новостей: {len(news_blocks)}")

            for item in news_blocks:
                try:
                    if item.name == 'a':
                        link_elem = item
                        inner_div = item.find('div', class_='inner')
                        title_elem = inner_div.find('p') if inner_div else None
                        date_elem = item.find('p', class_='date')
                    else:
                        link_elem = item.find('a', class_='news-item')
                        inner_div = item.find('div', class_='inner')
                        title_elem = inner_div.find('p') if inner_div else None
                        date_elem = item.find('p', class_='date')

                    if not link_elem:
                        continue

                    link = link_elem.get('href')
                    if link and not link.startswith('http'):
                        link = 'https://permkrai.ru' + link

                    if title_elem:
                        title = title_elem.get_text(strip=True)
                    else:
                        title = link_elem.get_text(strip=True) or "Новость"

                    if date_elem:
                        pub_date = date_elem.get_text(strip=True)
                        try:
                            pub_date = pub_date.replace('г.', '').strip()
                            pub_date = pub_date.replace(',', '')
                            dt = datetime.datetime.strptime(pub_date, "%d %B %Y %H:%M")
                            pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0500")
                        except:
                            pass
                    else:
                        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0500")

                    description = clean_description(link_elem.get_text(strip=True)[:500])
                    image = extract_image_html(item)

                    items.append({
                        'title': title,
                        'link': link,
                        'description': description,
                        'pub_date': pub_date,
                        'image': image,
                        'source': url
                    })
                except Exception as e:
                    print(f"  Ошибка при парсинге элемента: {e}")
                    continue

            print(f"  Спарсено {len(items)} новостей из HTML")
            return items

        # --- RSS-ПАРСИНГ (для v-kurse.ru и zwezda.su) ---
        feed = feedparser.parse(response.content)
        if feed.bozo:
            print(f"  Ошибка парсинга RSS: {feed.bozo_exception}")
            return []

        items = []
        for entry in feed.entries:
            title = entry.get('title', 'Без заголовка')
            link = entry.get('link', '')
            description = clean_description(entry.get('description', entry.get('summary', '')))
            pub_date = entry.get('published', entry.get('updated', ''))
            image = extract_image(entry)

            items.append({
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date,
                'image': image,
                'source': url
            })
        print(f"  Загружено {len(items)} новостей из RSS")
        return items

    except Exception as e:
        print(f"  ОШИБКА при загрузке {url}: {e}")
        return []

# --- 1. Скачиваем все новости ---
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

ET.SubElement(channel, "title").text = "Объединенная лента новостей"
ET.SubElement(channel, "description").text = "Новости с permkrai.ru, v-kurse.ru и zwezda.su"

for item in all_news:
    item_element = ET.SubElement(channel, "item")
    ET.SubElement(item_element, "title").text = item['title']
    ET.SubElement(item_element, "link").text = item['link']

    # --- УБИРАЕМ РУЧНОЕ ОБОРАЧИВАНИЕ В CDATA ---
    desc_element = ET.SubElement(item_element, "description")
    desc_element.text = item['description']

    pub_element = ET.SubElement(item_element, "pubDate")
    pub_element.text = str(item['pub_date'])

    if item.get('image'):
        enclosure = ET.SubElement(item_element, "enclosure")
        enclosure.set('url', item['image'])
        enclosure.set('type', 'image/jpeg')

tree = ET.ElementTree(rss_root)
tree.write('merged_feed.xml', encoding='utf-8', xml_declaration=True)

print(f"✅ RSS-лента создана с {len(all_news)} новостями!")
