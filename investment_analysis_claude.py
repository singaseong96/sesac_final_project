"""
투자 분석 파이프라인 (번역 없이 영어 원문 직접 분석)
────────────────────────────────────────────────────────
Step 1. 뉴스 감정 분석  (Claude API → 6개 레이블)
Step 2. 투자 판단       (Claude API → 한국어 출력)
Step 3. 결과 저장       → output/{SYMBOL}_analysis.json

감정 레이블
  Positive  전반적 호재
  Negative  전반적 악재
  Neutral   방향성 없음
  Growth    성장 기대 중심 긍정
  Risk      리스크/불확실성 강조
  Mixed     긍정 + 부정 혼재
"""

import json
import os
import re
import time
import glob
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

# ─────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────
MY_CLAUDE_API_KEY = ""
MODEL      = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1000
INPUT_DIR  = "./data"
OUTPUT_DIR = "./output"

SYMBOLS = ["JPM", "MSFT", "XOM", "NVDA", "TSM", "V", "GS", "CVX", "ABBV", "UNH"]
DAYS = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)

NOISE_KEYWORDS = ["cloudflare", "security service", "ray id", "access denied"]

# ─────────────────────────────────────────────────────────
# Claude API 호출
# ─────────────────────────────────────────────────────────
def call_claude(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    headers = {
        "Content-Type":      "application/json",
        "x-api-key":         MY_CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model":      MODEL,
        "max_tokens": max_tokens,
        "system":     system,
        "messages": [
            {"role": "user", "content": user},
        ],
    }
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers, json=body, timeout=60
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


# ─────────────────────────────────────────────────────────
# 파일 자동 탐색
# ─────────────────────────────────────────────────────────
def find_latest_file(symbol: str):
    pattern = os.path.join(INPUT_DIR, f"{symbol}_*.csv")
    files = [f for f in glob.glob(pattern) if "_translated" not in f]
    if not files:
        return None
    return max(files)


# ─────────────────────────────────────────────────────────
# Step 1. 감정 분석
# ─────────────────────────────────────────────────────────
def is_noise(content: str) -> bool:
    if not isinstance(content, str): return True
    return any(kw.lower() in content.lower() for kw in NOISE_KEYWORDS)

SENTIMENT_SYSTEM = """You are a financial news sentiment analysis expert.
Read the English news title and body, then output ONLY one of these 6 labels in Korean:

Labels:
Positive : 전반적 호재 (earnings beat, new product, partnership, etc.)
Negative : 전반적 악재 (earnings miss, lawsuit, regulation, decline, etc.)
Neutral  : 방향성 없는 중립 정보 (simple disclosure, shareholding change, etc.)
Growth   : 성장 기대 중심의 긍정 (AI/cloud expansion, market share growth, etc.)
Risk     : 리스크·불확실성 강조 (competition, macro uncertainty, regulatory risk, etc.)
Mixed    : 긍정과 부정이 혼재 (good earnings but weak guidance, etc.)

Rules:
- Positive vs Growth: simple good news → Positive / future growth momentum is key → Growth
- Negative vs Risk: already occurred bad news → Negative / potential uncertainty → Risk
- Output ONLY the label word. No explanation. No punctuation.
- Example output: Growth"""


def analyze_sentiment(title: str, content: str) -> str:
    if is_noise(content):
        user = f"Title: {title}"
    else:
        snippet = content[:800]
        user = f"Title: {title}\n\nBody:\n{snippet}"

    try:
        label = call_claude(SENTIMENT_SYSTEM, user, max_tokens=10)
        valid = {"Positive", "Negative", "Neutral", "Growth", "Risk", "Mixed"}
        cleaned = re.sub(r"[^a-zA-Z\s]", "", label)
        for word in cleaned.split():
            if word.capitalize() in valid:
                return word.capitalize()
        return "Neutral"
    except Exception as e:
        print(f"    감정분석 오류: {e}")
        return "Neutral"


def run_sentiment_analysis(df: pd.DataFrame) -> pd.DataFrame:
    labels = []
    total = len(df)
    for i, (_, row) in enumerate(df.iterrows(), 1):
        print(f"  [{i}/{total}] {str(row['title'])[:60]}...", end=" ")
        label = analyze_sentiment(row["title"], row.get("content", ""))
        labels.append(label)
        print(label)
        time.sleep(0.3)
    df = df.copy()
    df["sentiment"] = labels
    return df


# ─────────────────────────────────────────────────────────
# Step 2. 투자 판단
# ─────────────────────────────────────────────────────────
INVESTMENT_SYSTEM = """당신은 투자 분석을 수행하는 금융 애널리스트입니다.
영어 뉴스 데이터를 읽고 한국어로 분석 결과를 작성합니다.

다음 규칙을 반드시 준수하세요:
* 뉴스, 감정 분석 결과, 애널리스트 의견을 모두 통합하여 분석할 것
* 개별 뉴스가 아닌 전체 흐름과 트렌드를 기반으로 판단할 것
* 핵심 정보만 간결하게 정리할 것
* 정보 간의 인과관계를 명확히 설명할 것
* 상충되는 정보가 있을 경우 균형 있게 분석할 것
* 투자 관점에서 의미 있는 인사이트를 제시할 것
* 입력 데이터에 없는 내용을 추가하지 말 것
* 최종적으로 투자 여부에 대한 판단을 명확히 제시할 것
* 투자 판단은 반드시 분석 내용에 근거해야 하며, 단순 추측은 금지"""

INVESTMENT_USER_TMPL = """다음은 최근 {days}일간의 데이터입니다. 한국어로 분석하세요.

[뉴스 데이터 (영어 원문)]
{NEWS_BLOCK}

[감정 분석 결과]
{SENTIMENT_BLOCK}

[애널리스트 의견]
{ANALYST_BLOCK}

출력 형식:
[핵심 요약]
* 최근 {days}일간의 주요 이슈 요약

[전체 흐름 분석]
(시장 또는 해당 자산의 흐름을 종합적으로 설명)

[긍정 요인]
* ...

[부정 요인]
* ...

[투자 인사이트]
(투자 관점에서의 해석 및 시사점)

[투자 판단]
(투자 여부를 명확하게 제시: 투자 / 보류 / 비투자)

[판단 근거]
(왜 그런 결정을 내렸는지 분석 기반으로 설명)"""


def build_news_block(df: pd.DataFrame) -> str:
    lines = []
    for date, group in df.groupby(df["date"].dt.date):
        lines.append(f"\n── {date} ──")
        for _, row in group.iterrows():
            lines.append(f"  [{row['sentiment']}] {row['title']}")
    return "\n".join(lines)


def build_sentiment_block(df: pd.DataFrame) -> str:
    total  = len(df)
    counts = df["sentiment"].value_counts()
    lines  = [f"총 뉴스 {total}건 분석 결과:"]
    for label in ["Positive", "Growth", "Neutral", "Mixed", "Risk", "Negative"]:
        cnt = counts.get(label, 0)
        pct = round(cnt / total * 100, 1) if total else 0
        bar = "█" * int(pct / 5)
        lines.append(f"  {label:<10} {cnt:>3}건 ({pct:>5.1f}%) {bar}")
    lines.append("\n날짜별 감정 흐름:")
    for date, group in df.groupby(df["date"].dt.date):
        day_counts = group["sentiment"].value_counts().to_dict()
        summary = ", ".join(f"{k}:{v}" for k, v in day_counts.items())
        lines.append(f"  {date}: {summary}")
    return "\n".join(lines)


def build_analyst_block(data: dict) -> str:
    lines = []
    gc = data.get("analyst", {}).get("grades_consensus", {}).get("data", [])
    if gc:
        g = gc[0]
        lines.append("▶ 애널리스트 등급 합산")
        lines.append(f"  Strong Buy: {g.get('strongBuy',0)}  Buy: {g.get('buy',0)}"
                    f"  Hold: {g.get('hold',0)}  Sell: {g.get('sell',0)}"
                    f"  Strong Sell: {g.get('strongSell',0)}")
    pt = data.get("analyst", {}).get("price_target_consensus", {}).get("data", [])
    if pt:
        p = pt[0]
        lines.append("▶ 목표주가 컨센서스")
        lines.append(f"  High: ${p.get('targetHigh','N/A')}  Low: ${p.get('targetLow','N/A')}  "
                    f"Consensus: ${p.get('targetConsensus','N/A')}  Median: ${p.get('targetMedian','N/A')}")
    dcf = data.get("valuation", {}).get("dcf_valuation", {}).get("data", [])
    if dcf:
        d = dcf[0]
        lines.append("▶ DCF 내재가치")
        lines.append(f"  DCF: ${d.get('dcf','N/A')}  현재가: ${d.get('stockPrice','N/A')}")
    km = data.get("fundamental", {}).get("key_metrics_ttm", {}).get("data", [])
    if km:
        k = km[0]
        lines.append("▶ 핵심 밸류에이션 (TTM)")
        lines.append(f"  P/E: {k.get('peRatioTTM','N/A')}  P/B: {k.get('pbRatioTTM','N/A')}  "
                    f"EV/EBITDA: {k.get('evToEbitdaTTM','N/A')}  ROE: {k.get('roeTTM','N/A')}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────
def main(symbol):
    csv_path  = find_latest_file(symbol)
    json_path = os.path.join(INPUT_DIR, f"{symbol}.json")

    print("=" * 56)
    print(f" 투자 분석 파이프라인 — {symbol}")
    print("=" * 56)

    print("\n[1/4] 데이터 로드")
    if csv_path is None:
        print(f"  ⚠️ [{symbol}] CSV 파일 없음 → 건너뜀")
        return
    print(f"  파일: {csv_path}")

    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["content"] = df["content"].fillna("")
    df["title"]   = df["title"].fillna("")
    df = df[~df["title"].str.strip().isin(["url", ""])].reset_index(drop=True)
    df = df[~df["content"].str.lower().str.contains('|'.join(NOISE_KEYWORDS), na=False)]
    df = df.dropna(subset=["date"]).reset_index(drop=True)

    if df.empty:
        print(f"  ⚠️ [{symbol}] 유효한 데이터 없음 → 건너뜀")
        return

    fmp_data = {}
    if os.path.exists(json_path):
        with open(json_path, encoding="utf-8") as f:
            fmp_data = json.load(f)

    cutoff = df["date"].max() - timedelta(days=DAYS - 1)
    df_3d  = df[df["date"] >= cutoff.normalize()].copy()
    print(f"  뉴스 전체: {len(df)}건 → 최근 {DAYS}일: {len(df_3d)}건")

    print(f"\n[2/4] 감정 분석 ({len(df_3d)}건)")
    df_3d = run_sentiment_analysis(df_3d)

    sentiment_path = os.path.join(OUTPUT_DIR, f"{symbol}_sentiment.csv")
    df_3d.to_csv(sentiment_path, index=False, encoding="utf-8-sig")
    print(f"\n  → 감정 분석 저장: {sentiment_path}")

    print(f"\n[3/4] 투자 판단 (Claude 호출)")
    news_block      = build_news_block(df_3d)
    sentiment_block = build_sentiment_block(df_3d)
    analyst_block   = build_analyst_block(fmp_data)

    user_prompt = INVESTMENT_USER_TMPL.format(
        days           = DAYS,
        NEWS_BLOCK     = news_block,
        SENTIMENT_BLOCK= sentiment_block,
        ANALYST_BLOCK  = analyst_block,
    )

    judgment = call_claude(INVESTMENT_SYSTEM, user_prompt, max_tokens=1500)
    print("\n── 투자 판단 결과 ──")
    print(judgment)

    print(f"\n[4/4] 결과 저장")
    result = {
        "meta": {
            "symbol":        symbol,
            "analysis_date": datetime.now(timezone.utc).isoformat(),
            "news_period":   f"{df_3d['date'].min().date()} ~ {df_3d['date'].max().date()}",
            "news_count":    len(df_3d),
            "model":         MODEL,
        },
        "sentiment_summary": df_3d["sentiment"].value_counts().to_dict(),
        "sentiment_by_date": {
            str(date): group["sentiment"].value_counts().to_dict()
            for date, group in df_3d.groupby(df_3d["date"].dt.date)
        },
        "news_with_sentiment": df_3d[["date", "title", "url", "sentiment"]]
            .assign(date=df_3d["date"].astype(str))
            .to_dict(orient="records"),
        "analyst_context": {
            "news_block":      news_block,
            "sentiment_block": sentiment_block,
            "analyst_block":   analyst_block,
        },
        "investment_judgment": judgment,
    }

    out_path = os.path.join(OUTPUT_DIR, f"{symbol}_analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  → {out_path}")
    print("\n" + "=" * 56)


if __name__ == "__main__":
    for symbol in SYMBOLS:
        main(symbol)
