import requests
import json
import logging
from newspaper import Article
from base64 import b64decode
from bs4 import BeautifulSoup
import re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_constant(key):
    constants = {
        "oxylabs_scraper_username": "oxylabs_scraper_username",
        "oxylabs_scraper_password": "oxylabs_scraper_password+b",
        "zyte_api_url": "zyte_api_url",
        "zyte_api_key_wokelo": "zyte_api_key_wokelo",
    }
    return constants.get(key)


class ProxyScraper:
    '''
    This class is used to extract article content from a given URL using Oxylabs or Zyte proxy services.
    This scrapper specializes in tackling popups/overlays and cookie selectors that block the content.

    Usage:
        scraper = ProxyScraper()
        result = scraper.extract_article(url, use_proxy="zyte")

    Args (extract_article):
        url (str): URL of the article to extract content from.
        use_proxy (str) options = 'oxylabs', 'zyte': Default is "zyte".
        language (str): Default is "en".
    '''
    def __init__(self):
        self.oxylabs_username = get_constant("oxylabs_scraper_username")
        self.oxylabs_password = get_constant("oxylabs_scraper_password")
        self.zyte_api_url = get_constant("zyte_api_url")
        self.zyte_api_key = get_constant("zyte_api_key_wokelo")
        
    def extract_article(self, url, use_proxy="zyte", language="en"):
        try:
            logger.info(f"Starting article extraction from: {url}")

            if use_proxy == "oxylabs":
                response = self.f_oxylabs_proxy(url)
            elif use_proxy == "zyte":
                response = self.f_zyte_proxy(url)
            else:
                raise ValueError(f"Invalid proxy provider: {use_proxy}")

            if not response:
                return {"url": url, "error": "No response from proxy"}

            response = self.clean_input_text(response)
            cleaned_html = self.remove_overlays_and_clean_content(response)

            soup = BeautifulSoup(cleaned_html, 'html.parser')

            content_selectors = [
                'article', 
                '[itemprop="articleBody"]',
                '.article-content',
                '.article-body',
                '.story-content',
                '.post-content',
                'main article',
                'main .article',
                '.main-content article',
                '.content-area article',
                '.entry-content',
                '.post-body',
                '.story-body',
                '[role="main"]',
                '.caas-body',
                'main',
                '#main-content',
                '.main-content'
            ]

            def clean_text(text):
                if not text:
                    return ""
                text = re.sub(r'\n\s*\n', '\n\n', text)
                text = re.sub(r'\s+', ' ', text)
                text = re.sub(r'(?i)continue reading|read more|more for you|advertisement', '', text)
                return text.strip()

            full_content = []
            found_content = False

            for selector in content_selectors:
                contents = soup.select(selector)

                for content in contents:
                    for unwanted in content.find_all(['script', 'style', 'iframe', 'noscript', 'form']):
                        unwanted.decompose()

                    text = clean_text(content.get_text())

                    if text and len(text) > 100:
                        full_content.append(text)
                        found_content = True

                if found_content:
                    break

            if not found_content:
                article = Article(url, language=language)
                article.download(input_html=cleaned_html)
                article.parse()

                if article.text:
                    text = clean_text(article.text)
                    if text:
                        full_content.append(text)

            if not full_content:
                return {"url": url, "error": "No content found"}

            final_text = '\n\n'.join(full_content)
            final_text = clean_text(final_text)

            title = soup.find('h1')
            title = title.get_text().strip() if title else None

            if not title:
                title_selectors = [
                    '[itemprop="headline"]',
                    '.article-title',
                    '.entry-title',
                    '.post-title',
                    '.story-title'
                ]
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text().strip()
                        break

            date = None
            date_selectors = [
                '[itemprop="datePublished"]',
                '.article-date',
                '.post-date',
                '.published-date',
                'time'
            ]
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date = date_elem.get('datetime', date_elem.get_text().strip())
                    break

            authors = []
            author_selectors = [
                '[itemprop="author"]',
                '.article-author',
                '.post-author',
                '.author-name',
                '.byline'
            ]
            for selector in author_selectors:
                author_elems = soup.select(selector)
                for author_elem in author_elems:
                    author = author_elem.get_text().strip()
                    if author and author not in authors:
                        authors.append(author)

            return {
                "url": url,
                "title": title,
                "text": final_text,
                "authors": authors,
                "publish_date": date,
                "method": use_proxy
            }

        except Exception as e:
            logger.exception(f"Failed to extract article: {str(e)}")
            return {"url": url, "error": str(e)}

    def clean_input_text(self, text):
        return text.strip() if text else ""

    def remove_overlays_and_clean_content(self, html_content):
        if not html_content:
            return html_content

        soup = BeautifulSoup(html_content, 'html.parser')

        removal_patterns = {
            'ids': [
                'continue-reading', 'read-more', 'moreButton', 'more-content',
                'below-article', 'bottom-article', 'mid-article', 'article-interruption',
                'ad-insertion', 'advertisement', 'sponsored-content', 'taboola',
                'outbrain', 'related-articles', 'suggested-content', 'newsletter-signup',
                'subscription-prompt', 'more-for-you', 'trending-stories'
            ],
            'classes': [
                'continue-reading', 'read-more-button', 'article-break',
                'article-interstitial', 'ad-break', 'sponsored-content',
                'newsletter-unit', 'subscription-unit', 'paywall-container',
                'below-article-content', 'article-interruption', 'story-interrupt',
                'mid-article-unit', 'article-divide', 'more-for-you',
                'content-separation', 'story-break', 'loading-block'
            ],
            'text_patterns': [
                'continue reading',
                'read more',
                'more for you',
                'sponsored content',
                'advertisement',
                'recommended',
                'popular stories',
                'trending now',
                'you might like',
                'more stories',
                'more articles',
                'keep reading',
                'load more'
            ]
        }

        for pattern in removal_patterns['ids']:
            for element in soup.find_all(id=re.compile(pattern, re.I)):
                element.decompose()

        for pattern in removal_patterns['classes']:
            for element in soup.find_all(class_=re.compile(pattern, re.I)):
                element.decompose()

        for pattern in removal_patterns['text_patterns']:
            elements = soup.find_all(string=re.compile(pattern, re.I))
            for element in elements:
                parent = element.parent
                while parent and parent.name in ['button', 'a', 'div', 'section'] and len(parent.get_text()) < 1000:
                    next_parent = parent.parent
                    parent.decompose()
                    parent = next_parent

        return str(soup)

    def f_oxylabs_proxy(self, url):
        try:
            if "http://" not in url and "https://" not in url:
                url = "https://" + url

            payload = {
                "source": "universal",
                "url": url,
                "geo_location": "United States",
                "render": "html",
            }

            oxylabs_scraper_username = self.oxylabs_username
            oxylabs_scraper_password = self.oxylabs_password

            response = requests.request(
                'POST',
                'https://realtime.oxylabs.io/v1/queries',
                auth=(oxylabs_scraper_username, oxylabs_scraper_password),
                json=payload,
                timeout=120,
                allow_redirects=False
            )

            if response.status_code != 200:
                logger.warning(f"Error fetching oxylabs scraper results: Status: {response.status_code} {response.text}")
                return None

            content = response.json()['results'][0]['content']
            return self.remove_overlays_and_clean_content(content)
        except Exception as e:
            logger.warning(f"Oxylabs Scraper API failed: {e}")
            return None

    def f_zyte_proxy(self, url, req_type='get', data=None):
        if data is None:
            data = {}

        try:
            zyte_api_url = self.zyte_api_url
            zyte_api_key_wokelo = self.zyte_api_key

            if req_type == 'get':
                api_response = requests.post(
                    zyte_api_url,
                    auth=(zyte_api_key_wokelo, ''),
                    json={
                        "url": url,
                        "browserHtml": True
                    },
                    timeout=45,
                    allow_redirects=False
                )
                html_content = api_response.json()['browserHtml']
                return self.remove_overlays_and_clean_content(html_content)
            elif req_type == 'post':
                api_response = requests.post(
                    zyte_api_url,
                    auth=(zyte_api_key_wokelo, ""),
                    json={
                        "url": url,
                        "httpResponseBody": True,
                        "httpRequestMethod": "POST",
                        "httpRequestText": json.dumps(data),
                    },
                    timeout=45,
                    allow_redirects=False
                )
                return b64decode(api_response.json()["httpResponseBody"])
        except Exception as e:
            logger.warning(f"Zyte Failed: {str(e)}")
            return None
