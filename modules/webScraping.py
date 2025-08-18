import time
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


def get_structured_web_content_selenium(url: str) -> dict:
    print(f"URL açılıyor: {url}")

    options = Options()
    options.binary_location = "/usr/sbin/chromium-browser"
    options.add_argument("--headless")  # Arka planda çalıştır
    options.add_argument("--disable-gpu")  # No GPU
    options.add_argument("--no-sandbox")   # No Sandbox
    # ! Install driver via package manager
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(3)

    domain = urlparse(url).netloc

    def get_elements_text(by_tag):
        elements = driver.find_elements(By.TAG_NAME, by_tag)
        texts = [el.text.strip() for el in elements if el.text.strip()]
        print(f"<{by_tag}> etiketlerinden {len(texts)} adet içerik bulundu.")
        return texts

    result = {
        "title": driver.title,
        "meta_description": "",
        "headings": {
            "h1": get_elements_text("h1"),
            "h2": get_elements_text("h2"),
            "h3": get_elements_text("h3"),
        },
        "paragraphs": get_elements_text("p"),
        "div_texts": get_elements_text("div"),
        "lists": [],
        "tables": [],
        "emphasis": {
            "strong": get_elements_text("strong"),
            "em": get_elements_text("em")
        },
        "images_alt": [],
        "links": {
            "internal": [],
            "external": []
        }
    }

    # Meta description
    try:
        meta = driver.find_element(By.XPATH, "//meta[@name='description']")
        result["meta_description"] = meta.get_attribute("content")
        print(f"Meta description bulundu: {result['meta_description'][:80]}...")
    except Exception as e:
        print(f"Meta description bulunamadı: {e}")

    # Listeler
    for tag in ["ul", "ol"]:
        count = 0
        for el in driver.find_elements(By.TAG_NAME, tag):
            lis = el.find_elements(By.TAG_NAME, "li")
            for li in lis:
                text = li.text.strip()
                if text:
                    result["lists"].append(text)
                    count += 1
        print(f"<{tag}> listelerinden toplam {count} madde bulundu.")

    # Tablolar
    tables = driver.find_elements(By.TAG_NAME, "table")
    for table in tables:
        content = table.text.strip()
        if content:
            result["tables"].append(content)
    print(f"{len(tables)} adet <table> bulundu, {len(result['tables'])} tanesi dolu.")

    # Görsel alt metinleri
    imgs = driver.find_elements(By.TAG_NAME, "img")
    alt_count = 0
    for img in imgs:
        alt = img.get_attribute("alt")
        if alt:
            result["images_alt"].append(alt.strip())
            alt_count += 1
    print(f"{alt_count} adet <img alt='...'> bulundu.")

    # Linkler (internal vs external)
    internal_count, external_count = 0, 0
    for a in driver.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href")
        text = a.text.strip()
        if href:
            full_url = urljoin(url, href)
            link_info = {"text": text, "url": full_url}
            if domain in urlparse(full_url).netloc:
                result["links"]["internal"].append(link_info)
                internal_count += 1
            else:
                result["links"]["external"].append(link_info)
                external_count += 1
    print(f"{internal_count} iç link, {external_count} dış link bulundu.")

    driver.quit()
    print("Tarama tamamlandı.")
    return result
