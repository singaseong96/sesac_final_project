import time
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import os

# data 폴더 생성
os.makedirs("data", exist_ok=True)

TICKERS = ["NVDA", "MSFT", "TSM", "JPM", "V", "GS", "XOM", "CVX", "ABBV", "UNH"]

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def get_3days_news_links(ticker):
    query = f"{ticker} when:4d"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    res = requests.get(url, timeout=10)
    soup = BeautifulSoup(res.content, "xml")

    now = datetime.now()
    yesterday_end = now.replace(hour=23, minute=59) - timedelta(days=1)
    three_days_ago = now.replace(hour=0, minute=0) - timedelta(days=3)

    valid_items = []
    for item in soup.find_all("item"):
        pub_date = pd.to_datetime(item.pubDate.text).tz_localize(None)

        if three_days_ago <= pub_date <= yesterday_end:
            valid_items.append({
                "title": item.title.text,
                "link": item.link.text,
                "date": pub_date
            })

    return valid_items

def fast_extract(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "p"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        paras = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text()) > 50]
        content = " ".join(paras)

        return driver.current_url, content
    except:
        return url, ""

def main():
    driver = setup_driver()  # ⭐ driver 재사용 (성능 개선)

    try:
        for TICKER in TICKERS:
            print(f"\n🚀 {TICKER} 뉴스 수집 시작")
            
            news_items = get_3days_news_links(TICKER)
            print(f"🔎 대상 기사: {len(news_items)}건")

            results = []

            for i, item in enumerate(news_items):
                print(f"[{i+1}/{len(news_items)}] {item['title'][:40]}")

                real_url, content = fast_extract(driver, item['link'])

                if len(content) > 200:
                    results.append({
                        "ticker": TICKER,
                        "title": item['title'],
                        "date": item['date'],
                        "content": content,
                        "url": real_url
                    })
                    print("   ✅ 성공")
                else:
                    print("   ❌ 본문 부족")

            # ⭐ 종목별 저장 (핵심 수정)
            if results:
                filename = f"data/{TICKER}_{datetime.now().strftime('%y%m%d')}.csv"
                df = pd.DataFrame(results).sort_values(by='date', ascending=False)
                df.to_csv(filename, index=False, encoding="utf-8-sig")

                print(f"✨ {TICKER} 저장 완료 → {filename} ({len(results)}건)")
            else:
                print(f"❌ {TICKER}: 저장할 데이터 없음")

            # 👉 너무 빠르게 요청하면 차단될 수 있어서 약간 쉬기
            time.sleep(2)

        # 디버깅용
        print("\n📁 최종 파일 목록:", os.listdir("data"))

    finally:
        driver.quit()

if __name__ == "__main__":
    main()