import aiohttp
import asyncio
import urllib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromiumOptions
from selenium.webdriver.chrome.service import Service as ChromiumService
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from urllib.parse import urljoin, urlparse
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from webdriver_manager.firefox import GeckoDriverManager
# todo: implement caching in data/input/url


async def get_structured_web_content_selenium(url: str) -> dict:
    url = await _add_url_scheme(url)
    driver = await init_driver()

    await asyncio.to_thread(driver.get, url)
    await asyncio.sleep(3)

    domain = urlparse(url).netloc

    def get_elements_text(by_tag):
        elements = driver.find_elements(By.TAG_NAME, by_tag)
        return [el.text.strip() for el in elements if el.text.strip()]

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

    meta = driver.find_element(By.XPATH, "//meta[@name='description']")
    result["meta_description"] = meta.get_attribute("content")

    for tag in ["ul", "ol"]:
        for el in driver.find_elements(By.TAG_NAME, tag):
            lis = el.find_elements(By.TAG_NAME, "li")
            for li in lis:
                text = li.text.strip()
                if text:
                    result["lists"].append(text)

    for table in driver.find_elements(By.TAG_NAME, "table"):
        content = table.text.strip()
        if content:
            result["tables"].append(content)

    for img in driver.find_elements(By.TAG_NAME, "img"):
        alt = img.get_attribute("alt")
        if alt:
            result["images_alt"].append(alt.strip())

    for a in driver.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href")
        text = a.text.strip()
        if href:
            full_url = urljoin(url, href)
            link_info = {"text": text, "url": full_url}
            if domain in urlparse(full_url).netloc:
                result["links"]["internal"].append(link_info)
            else:
                result["links"]["external"].append(link_info)

    driver.quit()
    print("Tarama tamamlandi")
    return result


# Check HTTPS support
async def _check_https(url: str) -> bool:
    parsed_url = urllib.parse.urlparse(url)
    https_url = parsed_url._replace(scheme="https").geturl()
    timeout = aiohttp.ClientTimeout(total=5)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.head(https_url, allow_redirects=True) as response:
                    return response.status < 400
            except aiohttp.ClientResponseError as e:
                if e.status == 405:
                    async with session.get(https_url, allow_redirects=True) as response:
                        return response.status < 400
                return False
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


# Add scheme (http/https) if missing
async def _add_url_scheme(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ("http", "https"):
        return url
    test_https_url = "https://" + url
    return test_https_url if await _check_https(test_https_url) else "http://" + url


async def init_driver():
    try:
        try:
            return await init_chromium_driver()
        except Exception as chromium_err:
            print(f"Chromium got error: {chromium_err}")

        try:
            return await init_gecko_driver()
        except Exception as firefox_err:
            print(f"Firefox got an error: {firefox_err}")

    except Exception as driver_err:
        print("Driver failure cannot continue.")
        raise RuntimeError(driver_err)


async def init_chromium_driver():
    driver = webdriver.Chrome(service=ChromiumService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()))
    options = ChromiumOptions()
    options.add_argument("--headless=new")
    return driver


async def init_gecko_driver():
    options = FirefoxOptions()
    options.add_argument("--headless")
    driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
    return driver
