import os
import pandas as pd
import traceback
import requests
from datetime import datetime
import json

# ============================================================
MY_GEMINI_API_KEY = "여기에_Gemini_API_키_입력"
TICKER_LIST = ["JPM", "MSFT", "XOM", "NVDA", "TSM"]
MODEL_NAME  = "gemini-2.0-flash"
INPUT_DIR   = "data"
OUTPUT_DIR  = "data"
CHUNK_SIZE  = 5
# ============================================================

FILE_DATE_STR  = datetime.now().strftime("%y%m%d")
NOISE_KEYWORDS = ["cloudflare", "security service", "ray id", "access denied"]

def clean_text(text: str) -> str:
    if not isinstance(text, str): return ""
    return " ".join(text.replace("\n", " ").split()).strip()

def call_gemini(system: str, user: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={MY_GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    body = {
        "system_instruction": {
            "parts": [{"text": system}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": user}]}
        ],
        "generationConfig": {
            "maxOutputTokens": 16000,
        }
    }
    resp = requests.post(url, headers=headers, json=body, timeout=120)
    if not resp.ok:
        print(f"API 에러: {resp.status_code} / {resp.text}")
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def translate_chunk(chunk_df, ticker, start_idx):
    news_items = []
    for i, (_, row) in enumerate(chunk_df.iterrows()):
        item_text = f"[ID:{start_idx + i}] 날짜: {row.get('date')} | 제목: {row.get('title')} | 본문: {clean_text(str(row.get('content', '')))}"
        news_items.append(item_text)

    csv_data = "\n".join(news_items)

    system_prompt = """당신은 금융/경제 분야 전문 번역가입니다.
주어진 영어 금융 뉴스를 한국어로 번역하는 역할을 수행합니다.
- 원문 의미 왜곡 금지 / 누락·추가 금지
- 금융 용어 정확히 번역 / 고유명사 유지
- 모든 입력 데이터 빠짐없이 번역 / 입력 순서 유지"""

    user_prompt = f"""다음 금융 뉴스 데이터를 한국어로 번역하세요.

{csv_data}

아래 JSON 배열 형식으로만 출력하세요. 다른 텍스트 없이:
[
  {{"id": {start_idx}, "title": "번역된 제목", "content": "번역된 본문"}},
  {{"id": {start_idx+1}, "title": "번역된 제목", "content": "번역된 본문"}}
]"""

    try:
        content = call_gemini(system_prompt, user_prompt)

        # 코드블록 제거
        if "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            if content.startswith("json"):
                content = content[4:].strip()

        parsed = json.loads(content)
        return parsed

    except Exception as e:
        print(f"      ⚠️ 번역 실패 (ID {start_idx}~): {e}")
        return []


def process_ticker(ticker):
    csv_path = os.path.join(INPUT_DIR, f"{ticker}_{FILE_DATE_STR}.csv")
    if not os.path.exists(csv_path):
        print(f"  ⚠️ [{ticker}] 파일 없음: {csv_path}")
        return

    print(f"  🔍 [{ticker}] 데이터 처리 중...")
    df = pd.read_csv(csv_path)
    df = df[~df['content'].str.lower().str.contains('|'.join(NOISE_KEYWORDS), na=False)].reset_index(drop=True)

    all_translated_rows = []

    for i in range(0, len(df), CHUNK_SIZE):
        chunk_df = df.iloc[i: i + CHUNK_SIZE]
        print(f"    - {i+1}번부터 {min(i + CHUNK_SIZE, len(df))}번 뉴스 번역 중...")

        translated_data = translate_chunk(chunk_df, ticker, i)

        for item, (_, orig_row) in zip(translated_data, chunk_df.iterrows()):
            try:
                all_translated_rows.append({
                    "id":      orig_row.name + 1,
                    "ticker":  ticker,
                    "date":    orig_row.get("date"),
                    "title":   item.get("title") or item.get("제목") or "",
                    "content": item.get("content") or item.get("내용") or "",
                    "url":     orig_row.get("url")
                })
            except: continue

    if all_translated_rows:
        output_path = os.path.join(OUTPUT_DIR, f"{ticker}_{FILE_DATE_STR}_translated.csv")
        pd.DataFrame(all_translated_rows).to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"  ✅ [{ticker}] 완료 ({len(all_translated_rows)}건 저장)")


if __name__ == "__main__":
    try:
        for ticker in TICKER_LIST:
            process_ticker(ticker)
    except Exception as e:
        traceback.print_exc()
