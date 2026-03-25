import time
import csv
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

# data 폴더가 없으면 새로 생성 (이미 있으면 무시)
os.makedirs("data", exist_ok=True)

TICKERS = ["NVDA", "MSFT", "TSM", "JPM", "V", "GS", "XOM", "CVX", "ABBV", "UNH"]

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless") # 서버엔 화면이 없으므로 필수
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # GitHub 서버용 추가 옵션
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def get_3days_news_links(ticker):
    """어제 포함 3일치 링크 수집 (날짜 필터 적용)"""
    query = f"{ticker} when:4d" # 4일치 넉넉히 호출
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    
    res = requests.get(url, timeout=10)
    soup = BeautifulSoup(res.content, "xml")
    
    now = datetime.now()
    yesterday_end = now.replace(hour=23, minute=59) - timedelta(days=1)
    three_days_ago = now.replace(hour=0, minute=0) - timedelta(days=3)
    
    valid_items = []
    for item in soup.find_all("item"):
        pub_date = pd.to_datetime(item.pubDate.text).tz_localize(None)
        # 어제 포함 3일치만 필터링
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
        # [속도 향상 3] 3초 대기 대신, 본문 태그(<p>)가 나타날 때까지만 대기 (최대 5초)
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "p")))
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # 기사 본문 추출 (글자 수 기준 필터)
        paras = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text()) > 50]
        content = " ".join(paras)
        
        return driver.current_url, content
    except:
        return url, ""

def main():
    for TICKER in TICKERS:
        print(f"🚀 {TICKER} 어제 기준 3일치 뉴스 수집 (고속 모드)...")
        news_items = get_3days_news_links(TICKER)
        print(f"🔎 대상 기사: {len(news_items)}건 (범위: {datetime.now().date()-timedelta(days=3)} ~ {datetime.now().date()-timedelta(days=1)})")
        
        driver = setup_driver()
        results = []
        
        try:
            for i, item in enumerate(news_items):
                print(f"[{i+1}/{len(news_items)}] 추출 중: {item['title'][:30]}...")
                real_url, content = fast_extract(driver, item['link'])
                
                if len(content) > 200:
                    results.append({
                        "ticker": TICKER, "title": item['title'],
                        "date": item['date'], "content": content, "url": real_url
                    })
                    print("   ✅ 성공")
                else:
                    print("   ❌ 본문 부족")
                    
        finally:
            driver.quit()

    if results:
        filename = f"data/{TICKER}_{datetime.now().strftime('%y%m%d')}.csv"
        df = pd.DataFrame(results).sort_values(by='date', ascending=False)
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"\n✨ 완료! {filename} (총 {len(results)}건)")
    else:
        print("\n❌ 조건에 맞는 기사가 없습니다.")

if __name__ == "__main__":
    main()