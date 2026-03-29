"""
투자 분석용 LLM 평가 데이터 수집기 v3
────────────────────────────────────────
v2 대비 변경사항
  1. 429 자동 재시도 (지수 백오프: 2→4→8초)
  2. 이미 완료된 종목 스킵 (output/{SYMBOL}.json 존재 시)
  3. stock_grades_historical → 유지 (NYSE 종목은 정상, TSM 등 ADR은 null 허용)
  4. earnings_report         → 유지 (NYSE 정상, ADR null 허용)
  5. TOTAL 엔드포인트 수 기준을 실제 개수로 자동 계산
"""

import json
import time
import os
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
import certifi
from datetime import datetime

# ─────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────
API_KEY    = os.environ["FMP_API_KEY"]
OUTPUT_DIR = "./output"
DELAY      = 0.5          # 호출 간격(초) — 여유있게 0.5
MAX_RETRY  = 3            # 429 최대 재시도 횟수
TODAY      = datetime.today().strftime("%Y-%m-%d")
BASE       = "https://financialmodelingprep.com/stable"

STOCKS = {
    "테크_AI":         ["NVDA", "MSFT", "TSM"],
    "금융_핀테크":     ["JPM", "V", "GS"],
    "에너지_원자재":   ["XOM", "CVX"],
    "헬스케어_바이오": ["ABBV", "UNH"],
}

SYMBOL_TO_SECTOR = {s: sec for sec, syms in STOCKS.items() for s in syms}
ALL_SYMBOLS      = [s for syms in STOCKS.values() for s in syms]


# ─────────────────────────────────────────────────────────
# 슬림화 필드 정의 (LLM 핵심 필드만)
# ─────────────────────────────────────────────────────────
SLIM_FIELDS = {
    "grades_consensus": [
        "symbol", "strongBuy", "buy", "hold", "sell", "strongSell",
    ],
    "price_target_consensus": [
        "symbol", "targetHigh", "targetLow", "targetConsensus", "targetMedian",
    ],
    "analyst_estimates": [
        "symbol", "date",
        "estimatedRevenueLow", "estimatedRevenueHigh", "estimatedRevenueAvg",
        "estimatedEpsLow", "estimatedEpsHigh", "estimatedEpsAvg",
        "estimatedEbitdaAvg",
        "numberAnalystEstimatedRevenue", "numberAnalystsEstimatedEps",
    ],
    "stock_grades": [
        "symbol", "date", "gradingCompany", "previousGrade", "newGrade", "action",
    ],
    "stock_grades_historical": [
        "symbol", "date", "gradingCompany", "previousGrade", "newGrade", "action",
    ],
    "price_target_summary": [
        "symbol",
        "lastMonth", "lastMonthAvgPriceTarget",
        "lastQuarter", "lastQuarterAvgPriceTarget",
        "lastYear", "lastYearAvgPriceTarget",
        "allTime", "allTimeAvgPriceTarget",
    ],
    "key_metrics_ttm": [
        "symbol",
        "peRatioTTM", "pbRatioTTM", "evToEbitdaTTM", "evToSalesTTM",
        "priceToSalesRatioTTM", "priceToFreeCashFlowsRatioTTM",
        "roeTTM", "roicTTM", "returnOnTangibleAssetsTTM",
        "debtToEquityTTM", "netDebtToEBITDATTM",
        "freeCashFlowPerShareTTM", "dividendYieldTTM",
        "earningsYieldTTM", "freeCashFlowYieldTTM",
        "revenuePerShareTTM", "netIncomePerShareTTM",
        "marketCapTTM", "enterpriseValueTTM",
    ],
    "financial_ratios_ttm": [
        "symbol",
        "grossProfitMarginTTM", "operatingProfitMarginTTM", "netProfitMarginTTM",
        "returnOnAssetsTTM", "returnOnEquityTTM",
        "currentRatioTTM", "quickRatioTTM",
        "debtRatioTTM", "debtEquityRatioTTM",
        "interestCoverageTTM", "assetTurnoverTTM",
        "dividendYieldTTM", "payoutRatioTTM",
        "priceEarningsRatioTTM", "priceToBookRatioTTM",
        "priceToSalesRatioTTM", "freeCashFlowPerShareTTM",
    ],
    "financial_statement_growth": [
        "symbol", "date", "period",
        "revenueGrowth", "grossProfitGrowth", "operatingIncomeGrowth",
        "netIncomeGrowth", "epsgrowth", "freeCashFlowGrowth",
        "operatingCashFlowGrowth", "dividendsperShareGrowth",
        "revenueGrowth3Y", "netIncomeGrowth3Y", "epsgrowth3Y",
    ],
    "income_statement_annual": [
        "symbol", "date", "period",
        "revenue", "grossProfit", "operatingIncome", "netIncome",
        "eps", "epsDiluted", "ebitda",
        "grossProfitRatio", "operatingIncomeRatio", "netIncomeRatio",
        "researchAndDevelopmentExpenses", "weightedAverageShsOut",
    ],
    "cash_flow_statement_annual": [
        "symbol", "date", "period",
        "operatingCashFlow", "capitalExpenditure", "freeCashFlow",
        "netCashProvidedByOperatingActivities",
        "netCashUsedForInvestingActivites",
        "netCashUsedProvidedByFinancingActivities",
        "cashAtEndOfPeriod", "dividendsPaid", "commonStockRepurchased",
    ],
    "ratings_snapshot": [
        "symbol", "date", "rating", "ratingScore",
        "ratingDetailsDCFScore",  "ratingDetailsDCFRecommendation",
        "ratingDetailsROEScore",  "ratingDetailsROERecommendation",
        "ratingDetailsROAScore",  "ratingDetailsROARecommendation",
        "ratingDetailsDEScore",   "ratingDetailsDERecommendation",
        "ratingDetailsPEScore",   "ratingDetailsPERecommendation",
        "ratingDetailsPBScore",   "ratingDetailsPBRecommendation",
    ],
    "financial_scores": [
        "symbol", "altmanZScore", "piotroskiScore",
        "workingCapital", "totalAssets", "retainedEarnings",
        "ebit", "marketCap", "totalLiabilities", "revenue",
    ],
    "dcf_valuation": [
        "symbol", "date", "dcf", "stockPrice",
    ],
    "enterprise_values": [
        "symbol", "date",
        "stockPrice", "numberOfShares", "marketCapitalization",
        "minusCashAndCashEquivalents", "addTotalDebt", "enterpriseValue",
    ],
    "owner_earnings": [
        "symbol", "date",
        "averagePPE", "maintenanceCapex", "ownersEarnings",
        "growthCapex", "ownersEarningsPerShare",
    ],
    "sector_pe_snapshot": [
        "date", "sector", "exchange", "pe",
    ],
    "treasury_rates": [
        "date", "month1", "month3", "month6",
        "year1", "year2", "year5", "year10", "year30",
    ],
    "earnings_report": [
        "symbol", "date", "eps", "epsEstimated",
        "revenue", "revenueEstimated", "period",
    ],
}


# ─────────────────────────────────────────────────────────
# 엔드포인트 정의
# ─────────────────────────────────────────────────────────
ENDPOINTS = {
    # ── 애널리스트 (필수) ──────────────────────────────────
    "grades_consensus": {
        "url":     f"{BASE}/grades-consensus?symbol={{symbol}}&apikey={API_KEY}",
        "section": "analyst",
        "desc":    "애널리스트 등급 합산 (Strong Buy ~ Strong Sell)",
    },
    "price_target_consensus": {
        "url":     f"{BASE}/price-target-consensus?symbol={{symbol}}&apikey={API_KEY}",
        "section": "analyst",
        "desc":    "목표주가 컨센서스 (High/Low/Median/Consensus)",
    },
    "analyst_estimates": {
        "url":     f"{BASE}/analyst-estimates?symbol={{symbol}}&period=annual&page=0&limit=3&apikey={API_KEY}",
        "section": "analyst",
        "desc":    "향후 실적 추정치 (매출·EPS·EBITDA) — 3개년",
    },
    # ── 애널리스트 (권장) ──────────────────────────────────
    "stock_grades": {
        "url":     f"{BASE}/grades?symbol={{symbol}}&limit=10&apikey={API_KEY}",
        "section": "analyst",
        "desc":    "개별 증권사 최신 등급 (최근 10건)",
    },
    "stock_grades_historical": {
        "url":     f"{BASE}/grades-historical?symbol={{symbol}}&limit=20&apikey={API_KEY}",
        "section": "analyst",
        "desc":    "등급 업/다운그레이드 이력 (최근 20건, ADR은 null 허용)",
    },
    "price_target_summary": {
        "url":     f"{BASE}/price-target-summary?symbol={{symbol}}&apikey={API_KEY}",
        "section": "analyst",
        "desc":    "1·3·6개월 평균 목표주가 추이",
    },
    # ── 펀더멘털 (필수) ────────────────────────────────────
    "key_metrics_ttm": {
        "url":     f"{BASE}/key-metrics-ttm?symbol={{symbol}}&apikey={API_KEY}",
        "section": "fundamental",
        "desc":    "핵심 밸류에이션 지표 TTM",
    },
    "financial_ratios_ttm": {
        "url":     f"{BASE}/ratios-ttm?symbol={{symbol}}&apikey={API_KEY}",
        "section": "fundamental",
        "desc":    "재무 비율 TTM",
    },
    # ── 펀더멘털 (권장) ────────────────────────────────────
    "financial_statement_growth": {
        "url":     f"{BASE}/financial-growth?symbol={{symbol}}&limit=3&apikey={API_KEY}",
        "section": "fundamental",
        "desc":    "매출·EPS·FCF 성장률 YoY (최근 3개년)",
    },
    # ✅ income/cashflow TTM(402) → 연간 최신 1건으로 대체
    "income_statement_annual": {
        "url":     f"{BASE}/income-statement?symbol={{symbol}}&period=annual&limit=1&apikey={API_KEY}",
        "section": "fundamental",
        "desc":    "손익계산서 연간 최신 (income_statement_ttm 대체)",
    },
    "cash_flow_statement_annual": {
        "url":     f"{BASE}/cash-flow-statement?symbol={{symbol}}&period=annual&limit=1&apikey={API_KEY}",
        "section": "fundamental",
        "desc":    "현금흐름표 연간 최신 (cash_flow_statement_ttm 대체)",
    },
    # ── 밸류에이션 (필수) ──────────────────────────────────
    "ratings_snapshot": {
        "url":     f"{BASE}/ratings-snapshot?symbol={{symbol}}&apikey={API_KEY}",
        "section": "valuation",
        "desc":    "FMP 종합 등급 + 항목별 점수",
    },
    "financial_scores": {
        "url":     f"{BASE}/financial-scores?symbol={{symbol}}&apikey={API_KEY}",
        "section": "valuation",
        "desc":    "Altman Z-Score + Piotroski F-Score",
    },
    "dcf_valuation": {
        "url":     f"{BASE}/discounted-cash-flow?symbol={{symbol}}&apikey={API_KEY}",
        "section": "valuation",
        "desc":    "DCF 내재가치 vs 현재가",
    },
    # ── 밸류에이션 (선택) ──────────────────────────────────
    "enterprise_values": {
        "url":     f"{BASE}/enterprise-values?symbol={{symbol}}&limit=1&apikey={API_KEY}",
        "section": "valuation",
        "desc":    "EV, EV/EBITDA, EV/Sales",
    },
    "owner_earnings": {
        "url":     f"{BASE}/owner-earnings?symbol={{symbol}}&limit=1&apikey={API_KEY}",
        "section": "valuation",
        "desc":    "오너이익 (버핏식 실질 수익력)",
    },
    # ── 시장 맥락 (공용 — symbol 불필요) ──────────────────
    "sector_pe_snapshot": {
        "url":     f"{BASE}/sector-pe-snapshot?date={TODAY}&apikey={API_KEY}",
        "section": "market_context",
        "desc":    "섹터별 PER 스냅샷 (오늘 기준)",
        "shared":  True,
    },
    "treasury_rates": {
        "url":     f"{BASE}/treasury-rates?apikey={API_KEY}",
        "section": "market_context",
        "desc":    "미국 국채 금리 (2Y·10Y·30Y …)",
        "shared":  True,
    },
    # ── 시장 맥락 (종목별, ADR null 허용) ─────────────────
    "earnings_report": {
        "url":     f"{BASE}/earnings?symbol={{symbol}}&limit=8&apikey={API_KEY}",
        "section": "market_context",
        "desc":    "EPS 실제치 vs 추정치 — 최근 8분기 (ADR은 null 허용)",
    },
}

TOTAL = len(ENDPOINTS)  # 공용 포함 전체 엔드포인트 수


# ─────────────────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────────────────
def fetch(url: str):
    """
    URL 호출 → JSON 반환.
    - 429: 지수 백오프 후 MAX_RETRY 회 재시도
    - 그 외 오류: None 반환
    """
    for attempt in range(MAX_RETRY):
        try:
            res = urlopen(url, cafile=certifi.where(), timeout=15)
            return json.loads(res.read().decode("utf-8"))

        except HTTPError as e:
            if e.code == 429:
                wait = 2 ** (attempt + 1)   # 2 → 4 → 8초
                print(f"429 Rate limit — {wait}초 대기 후 재시도 ({attempt+1}/{MAX_RETRY})...",
                      end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"✗ HTTP {e.code}")
                return None

        except (URLError, json.JSONDecodeError) as e:
            print(f"✗ {e}")
            return None

    print(f"✗ {MAX_RETRY}회 재시도 후 실패")
    return None


def slim(key: str, raw):
    """SLIM_FIELDS에 정의된 핵심 필드만 추출."""
    fields = SLIM_FIELDS.get(key)
    if fields is None or raw is None:
        return raw

    def pick(obj):
        return {k: obj[k] for k in fields if k in obj} if isinstance(obj, dict) else obj

    return [pick(item) for item in raw] if isinstance(raw, list) else pick(raw)


def is_ok(data) -> bool:
    return data is not None and data != [] and data != {}


def fetch_shared() -> dict:
    shared = {}
    for key, cfg in ENDPOINTS.items():
        if cfg.get("shared"):
            print(f"  [공용] {key} ...", end=" ")
            raw  = fetch(cfg["url"])
            data = slim(key, raw)
            shared[key] = {"description": cfg["desc"], "data": data}
            print("✓" if is_ok(data) else "✗")
            time.sleep(DELAY)
    return shared


def fetch_symbol(symbol: str, shared: dict) -> dict:
    result = {
        "meta": {
            "symbol":       symbol,
            "sector":       SYMBOL_TO_SECTOR.get(symbol, ""),
            "collected_at": datetime.utcnow().isoformat() + "Z",
            "api_version":  "v3",
        },
        "analyst":        {},
        "fundamental":    {},
        "valuation":      {},
        "market_context": {},
    }

    for key, cfg in ENDPOINTS.items():
        section = cfg["section"]

        if cfg.get("shared"):
            result[section][key] = shared.get(key, {})
            continue

        url = cfg["url"].format(symbol=symbol)
        print(f"    {key} ...", end=" ")
        raw  = fetch(url)
        data = slim(key, raw)
        print("✓" if is_ok(data) else "✗")

        result[section][key] = {"description": cfg["desc"], "data": data}
        time.sleep(DELAY)

    return result


# ─────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 58)
    print(" FMP 데이터 수집기 v3")
    print(f" 종목 {len(ALL_SYMBOLS)}개 / 엔드포인트 {TOTAL}개")
    print(f" 429 재시도: 최대 {MAX_RETRY}회 (지수 백오프)")
    print(f" 이미 완료된 종목: 스킵")
    print(f" 출력: {OUTPUT_DIR}/{{SYMBOL}}.json")
    print("=" * 58)

    # ── Step 1: 공용 데이터 ───────────────────────────────
    print("\n[Step 1] 공용 데이터 수집")
    shared = fetch_shared()

    # ── Step 2: 종목별 수집 ───────────────────────────────
    print("\n[Step 2] 종목별 수집\n")
    summary = []

    for sector, symbols in STOCKS.items():
        print(f"▶ {sector}")
        for symbol in symbols:
            out_path = os.path.join(OUTPUT_DIR, f"{symbol}.json")

            # ✅ 이미 완료된 종목 스킵
            if os.path.exists(out_path):
                size_kb = os.path.getsize(out_path) // 1024
                print(f"  [{symbol}] 이미 존재 — 스킵 ({size_kb} KB)")
                # 요약용 ok 수 계산
                with open(out_path, encoding="utf-8") as f:
                    cached = json.load(f)
                ok = sum(
                    1 for sec in ["analyst", "fundamental", "valuation", "market_context"]
                    for v in cached[sec].values()
                    if isinstance(v, dict) and is_ok(v.get("data"))
                )
                summary.append((symbol, sector, ok, size_kb, out_path, "SKIP"))
                continue

            print(f"  [{symbol}]")
            data = fetch_symbol(symbol, shared)

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            ok = sum(
                1 for sec in ["analyst", "fundamental", "valuation", "market_context"]
                for v in data[sec].values()
                if isinstance(v, dict) and is_ok(v.get("data"))
            )
            size_kb = os.path.getsize(out_path) // 1024
            summary.append((symbol, sector, ok, size_kb, out_path, "NEW"))
            print(f"  → 저장 완료 ({ok}/{TOTAL} 성공, ~{size_kb} KB)\n")

    # ── 요약 ─────────────────────────────────────────────
    print("=" * 62)
    print(f" {'Symbol':<7} {'섹터':<16} {'성공':>8} {'크기':>7}  상태")
    print("-" * 62)
    for sym, sec, ok, kb, _, status in summary:
        flag = "✓ 신규" if status == "NEW" else "→ 스킵"
        print(f" {sym:<7} {sec:<16} {ok:>5}/{TOTAL} {kb:>5} KB  {flag}")
    print("=" * 62)


if __name__ == "__main__":
    main()
