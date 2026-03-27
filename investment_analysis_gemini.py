"""
투자 분석 파이프라인
────────────────────────────────────────────────────────
Step 1. 뉴스 감정 분석  (Gemini API → 6개 레이블)
Step 2. 투자 판단       (Gemini API → 시스템/유저 프롬프트)
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
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

# ─────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────
MY_GEMINI_API_KEY = "여기에_Gemini_API_키_입력"
MODEL      = "gemini-2.0-flash"
MAX_TOKENS = 1000
OUTPUT_DIR = "./output"

SYMBOLS = ["JPM", "MSFT", "XOM", "NVDA", "TSM", "V", "GS", "CVX", "ABBV", "UNH"]

# 최근 N일 필터
DAYS = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────
# Gemini API 호출
# ─────────────────────────────────────────────────────────
def call_gemini(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={MY_GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    body = {
        "system_instruction": {
            "parts": [{"text": system}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": user}]}
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
        }
    }
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


# ─────────────────────────────────────────────────────────
# Step 1. 감정 분석
# ─────────────────────────────────────────────────────────
BLOCKED_KEYWORDS = [
    "security service",
    "banned you",
    "cookie tech",
    "Cloudflare",
    "you are using automation",
    "Please make sure your browser",
    "access to this page has been denied",
]

def is_blocked_content(content: str) -> bool:
    """Cloudflare 등 차단 페이지 여부 판별"""
    return any(kw.lower() in content.lower() for kw in BLOCKED_KEYWORDS)


SENTIMENT_SYSTEM = """당신은 금융 뉴스 감정 분석 전문가입니다.
뉴스 제목과 본문을 읽고 아래 6개 레이블 중 하나만 출력하세요.

레이블 정의:
Positive : 전반적 호재 (실적 호조, 신제품, 파트너십 등)
Negative : 전반적 악재 (실적 부진, 소송, 규제, 하락 등)
Neutral  : 방향성 없는 중립 정보 (단순 공시, 지분 변동 등)
Growth   : 성장 기대 중심의 긍정 (AI·클라우드 확장, 시장 점유율 상승 등)
Risk     : 리스크·불확실성 강조 (경쟁 심화, 매크로 불확실성, 규제 위험 등)
Mixed    : 긍정과 부정이 혼재 (실적은 좋으나 가이던스 부진 등)

구분 기준:
Positive vs Growth : 단순 호재 → Positive / 미래 성장 모멘텀이 핵심 → Growth
Negative vs Risk   : 이미 발생한 악재 → Negative / 잠재적 불확실성·우려 → Risk

출력 규칙:
- 반드시 위 6개 레이블 중 하나만 출력
- 설명, 부연, 이유 일절 금지
- 예시 출력: Growth"""


def analyze_sentiment(title: str, content: str) -> str:
    if not isinstance(content, str):
        content = ""

    if not content or is_blocked_content(content):
        user = f"제목: {title}"
    else:
        snippet = content[:800]
        user = f"제목: {title}\n\n본문:\n{snippet}"

    try:
        label = call_gemini(SENTIMENT_SYSTEM, user, max_tokens=300)

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
    """DataFrame 전체에 감정 분석 적용"""
    labels = []
    total  = len(df)
    for i, (_, row) in enumerate(df.iterrows(), 1):
        print(f"  [{i}/{total}] {row['title'][:60]}...", end=" ")
        label = analyze_sentiment(row["title"], row.get("content", ""))
        labels.append(label)
        print(label)
        time.sleep(0.2)
    df = df.copy()
    df["sentiment"] = labels
    return df


# ─────────────────────────────────────────────────────────
# Step 2. 투자 판단 프롬프트 구성
# ─────────────────────────────────────────────────────────
INVESTMENT_SYSTEM = """당신은 투자 분석을 수행하는 금융 애널리스트입니다.
주어진 데이터를 기반으로 최근 3일간의 정보를 종합 분석하고,
투자 관점에서 의미 있는 인사이트와 의사결정을 도출하는 역할을 수행합니다.

다음 규칙을 반드시 준수하세요:
* 뉴스, 감정 분석 결과, 애널리스트 의견을 모두 통합하여 분석할 것
* 개별 뉴스가 아닌 전체 흐름과 트렌드를 기반으로 판단할 것
* 핵심 정보만 간결하게 정리할 것 (불필요한 설명 제거)
* 정보 간의 인과관계를 명확히 설명할 것
* 상충되는 정보가 있을 경우 이를 함께 고려하여 균형 있게 분석할 것
* 투자 관점에서 의미 있는 인사이트를 제시할 것
* 입력 데이터에 없는 내용을 추가하지 말 것
* 최종적으로 투자 여부에 대한 판단을 명확히 제시할 것
* 투자 판단은 반드시 분석 내용에 근거해야 하며, 단순 추측은 금지"""

INVESTMENT_USER_TMPL = """다음은 최근 3일간의 데이터입니다.
이 데이터를 종합적으로 분석하여 투자 인사이트와 투자 판단을 도출하세요.

[뉴스 데이터]
{NEWS_3DAY}

[감정 분석 결과]
{SENTIMENT_3DAY}

[애널리스트 의견]
{ANALYST_3DAY}

출력 형식:
[핵심 요약]
* 최근 3일간의 주요 이슈 요약

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
    """날짜별 뉴스 + 감정 레이블 텍스트 블록 생성"""
    lines = []
    for date, group in df.groupby(df["date"].dt.date):
        lines.append(f"\n── {date} ──")
        for _, row in group.iterrows():
            lines.append(f"  [{row['sentiment']}] {row['title']}")
    return "\n".join(lines)


def build_sentiment_block(df: pd.DataFrame) -> str:
    """감정 레이블 집계 요약 블록 생성"""
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
    """JSON에서 애널리스트 핵심 데이터 추출 → 텍스트 블록"""
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
        lines.append(f"  High: ${p.get('targetHigh','N/A')}  "
                    f"Low: ${p.get('targetLow','N/A')}  "
                    f"Consensus: ${p.get('targetConsensus','N/A')}  "
                    f"Median: ${p.get('targetMedian','N/A')}")

    ae = data.get("analyst", {}).get("analyst_estimates", {}).get("data", [])
    if ae:
        a = ae[0]
        lines.append(f"▶ 실적 추정치 ({a.get('date','')[:7]})")
        rev = a.get("estimatedRevenueAvg", 0)
        eps = a.get("estimatedEpsAvg", 0)
        lines.append(f"  예상 매출: ${rev/1e9:.1f}B  예상 EPS: ${eps:.2f}")

    dcf = data.get("valuation", {}).get("dcf_valuation", {}).get("data", [])
    if dcf:
        d = dcf[0]
        lines.append("▶ DCF 내재가치")
        lines.append(f"  DCF: ${d.get('dcf','N/A')}  현재가: ${d.get('stockPrice','N/A')}")

    rs = data.get("valuation", {}).get("ratings_snapshot", {}).get("data", [])
    if rs:
        r = rs[0]
        lines.append("▶ FMP 종합 등급")
        lines.append(f"  등급: {r.get('rating','N/A')}  점수: {r.get('ratingScore','N/A')}")

    km = data.get("fundamental", {}).get("key_metrics_ttm", {}).get("data", [])
    if km:
        k = km[0]
        lines.append("▶ 핵심 밸류에이션 (TTM)")
        lines.append(f"  P/E: {k.get('peRatioTTM','N/A')}  "
                    f"P/B: {k.get('pbRatioTTM','N/A')}  "
                    f"EV/EBITDA: {k.get('evToEbitdaTTM','N/A')}  "
                    f"ROE: {k.get('roeTTM','N/A')}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────
def main(SYMBOL):
    FILE_DATE_STR = datetime.now().strftime("%y%m%d")
    CSV_PATH  = f"./data/{SYMBOL}_{FILE_DATE_STR}_translated.csv"
    JSON_PATH = f"./data/{SYMBOL}.json"

    print("=" * 56)
    print(f" 투자 분석 파이프라인 — {SYMBOL}")
    print("=" * 56)

    print("\n[1/4] 데이터 로드")

    if not os.path.exists(CSV_PATH):
        print(f"  ⚠️ [{SYMBOL}] CSV 파일 없음: {CSV_PATH} → 건너뜀")
        return

    df = pd.read_csv(CSV_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["content"] = df["content"].fillna("")
    df["title"]   = df["title"].fillna("")
    df = df[~df["title"].str.strip().isin(["url", ""])].reset_index(drop=True)
    df = df.dropna(subset=["date"])

    if df.empty:
        print(f"  ⚠️ [{SYMBOL}] 유효한 데이터 없음 → 건너뜀")
        return

    with open(JSON_PATH, encoding="utf-8") as f:
        fmp_data = json.load(f)

    cutoff = df["date"].max() - timedelta(days=DAYS - 1)
    df_3d  = df[df["date"] >= cutoff.normalize()].copy()
    print(f"  뉴스 전체: {len(df)}건 → 최근 {DAYS}일: {len(df_3d)}건")
    print(f"  기간: {df_3d['date'].min().date()} ~ {df_3d['date'].max().date()}")

    print(f"\n[2/4] 감정 분석 ({len(df_3d)}건)")
    df_3d = run_sentiment_analysis(df_3d)

    sentiment_path = os.path.join(OUTPUT_DIR, f"{SYMBOL}_sentiment.csv")
    df_3d.to_csv(sentiment_path, index=False, encoding="utf-8-sig")
    print(f"\n  → 감정 분석 저장: {sentiment_path}")
    print(f"  레이블 분포:\n{df_3d['sentiment'].value_counts().to_string()}")

    print(f"\n[3/4] 투자 판단 (Gemini 호출)")

    news_block      = build_news_block(df_3d)
    sentiment_block = build_sentiment_block(df_3d)
    analyst_block   = build_analyst_block(fmp_data)

    user_prompt = INVESTMENT_USER_TMPL.format(
        NEWS_3DAY      = news_block,
        SENTIMENT_3DAY = sentiment_block,
        ANALYST_3DAY   = analyst_block,
    )

    judgment = call_gemini(INVESTMENT_SYSTEM, user_prompt, max_tokens=1500)
    print("\n── 투자 판단 결과 ──")
    print(judgment)

    print(f"\n[4/4] 결과 저장")

    result = {
        "meta": {
            "symbol":        SYMBOL,
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

    out_path = os.path.join(OUTPUT_DIR, f"{SYMBOL}_analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  → {out_path}")
    print("\n" + "=" * 56)
    print(" 완료")
    print("=" * 56)


if __name__ == "__main__":
    for SYMBOL in SYMBOLS:
        main(SYMBOL)
