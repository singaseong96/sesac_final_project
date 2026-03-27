"""
주식 투자 분석 대시보드
구성: 투자 판단 → 애널리스트 등급 → 감정 분석 → 뉴스 목록
실행: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json, os, re

# ─────────────────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="주식 투자 분석",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

OUTPUT_DIR = "./output"

STOCKS = {
    "테크·AI":         ["NVDA", "MSFT", "TSM"],
    "금융·핀테크":     ["JPM", "V", "GS"],
    "에너지·원자재":   ["XOM", "CVX"],
    "헬스케어·바이오": ["ABBV", "UNH"],
}
COMPANY_NAME = {
    "NVDA": "Nvidia",       "MSFT": "Microsoft",  "TSM": "TSMC",
    "JPM":  "JPMorgan",     "V":    "Visa",        "GS":  "Goldman Sachs",
    "XOM":  "ExxonMobil",   "CVX":  "Chevron",
    "ABBV": "AbbVie",       "UNH":  "UnitedHealth",
}

SENTIMENT_COLOR = {
    "Growth":   "#1D9E75", "Positive": "#26A69A", "Neutral":  "#888780",
    "Mixed":    "#BA7517", "Risk":     "#E88B2A", "Negative": "#E24B4A",
}
SENTIMENT_KO = {
    "Growth": "성장 기대", "Positive": "긍정",   "Neutral":  "중립",
    "Mixed":  "혼재",      "Risk":     "리스크",  "Negative": "부정",
}

# ─────────────────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 주식 투자 분석")
    st.markdown("---")
    sector = st.selectbox("섹터", list(STOCKS.keys()))
    symbol = st.selectbox(
        "종목", STOCKS[sector],
        format_func=lambda s: f"{s}  |  {COMPANY_NAME.get(s, '')}",
    )
    st.markdown("---")
    st.caption("데이터: FMP · OpenAI")

company = COMPANY_NAME.get(symbol, symbol)

# ─────────────────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────────────────
def load_json(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None

def load_csv(path):
    if os.path.exists(path):
        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"])
        return df
    return None

def safe_get(d, section, key):
    return (d or {}).get(section, {}).get(key, {}).get("data") or []

fmp      = load_json(os.path.join(OUTPUT_DIR, f"{symbol}.json"))
df_sent  = load_csv(os.path.join(OUTPUT_DIR, f"{symbol}_sentiment.csv"))
analysis = load_json(os.path.join(OUTPUT_DIR, f"{symbol}_analysis.json"))

# ─────────────────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────────────────
st.title(f"📊 {symbol}  |  {company}")
st.caption(f"섹터: {sector}  ·  데이터 기준: FMP + OpenAI 분석")
st.markdown("---")

# ═════════════════════════════════════════════════════════
# 1. 투자 판단
# ═════════════════════════════════════════════════════════
st.header("🎯 투자 판단")

if analysis is None:
    st.warning(f"`output/{symbol}_analysis.json` 파일이 없습니다. investment_analysis.py를 먼저 실행하세요.")
else:
    meta = analysis.get("meta", {})
    m1, m2, m3 = st.columns(3)
    m1.metric("분석 종목", meta.get("symbol", "-"))
    m2.metric("뉴스 기간", meta.get("news_period", "-"))
    m3.metric("분석 뉴스", f"{meta.get('news_count', 0)}건")

    st.markdown("")

    # 투자 판단 배너
    jt = analysis.get("investment_judgment", "")

    # ✅ 투자 판단 섹션만 잘라서 키워드 탐색 (오탐 방지)
    verdict_section = ""
    escaped = re.escape("투자 판단"[0:])
    m = re.search(r'\[\s*투자 판단\s*\](.*?)(?=\[|$)', jt, re.DOTALL)
    if m:
        verdict_section = m.group(1)

    verdict, v_fn = "⏸️ 보류", st.warning
    if "비투자" in verdict_section:
        verdict, v_fn = "❌ 비투자", st.error
    elif "투자" in verdict_section and "비투자" not in verdict_section:
        verdict, v_fn = "✅ 투자", st.success
    elif "보류" in verdict_section:
        verdict, v_fn = "⏸️ 보류", st.warning

    v_fn(f"### {verdict}")

    # 섹션 파싱
    SECTION_LIST = [
        ("[핵심 요약]",     "📌 핵심 요약"),
        ("[전체 흐름 분석]","🔍 전체 흐름 분석"),
        ("[긍정 요인]",     "✅ 긍정 요인"),
        ("[부정 요인]",     "⚠️ 부정 요인"),
        ("[투자 인사이트]", "💡 투자 인사이트"),
        ("[투자 판단]",     "🎯 투자 판단"),
        ("[판단 근거]",     "📋 판단 근거"),
    ]
    skeys = [s[0] for s in SECTION_LIST]

    def split_sec(text):
        result = {}
        # ✅ 정규식으로 앞뒤 공백·마크다운 기호 무시하고 섹션 탐색
        pattern = r'\[{key}\]'
        for i, key in enumerate(skeys):
            # **[핵심 요약]**, [ 핵심 요약 ] 등 모두 허용
            escaped = re.escape(key[1:-1])  # 괄호 안 텍스트만 추출
            start_match = re.search(rf'\*{{0,2}}\[\s*{escaped}\s*\]\*{{0,2}}', text)
            if not start_match:
                continue
            start = start_match.end()

            # 다음 섹션 시작 위치 탐색
            nxt_pos = len(text)
            for nxt_key in skeys[i+1:]:
                escaped_nxt = re.escape(nxt_key[1:-1])
                nxt_match = re.search(rf'\*{{0,2}}\[\s*{escaped_nxt}\s*\]\*{{0,2}}', text)
                if nxt_match:
                    nxt_pos = nxt_match.start()
                    break

            result[key] = text[start:nxt_pos].strip()
        return result

    secs   = split_sec(jt)
    left_k = {"[핵심 요약]", "[긍정 요인]", "[투자 인사이트]", "[투자 판단]"}
    cl, cr = st.columns(2)

    for key, title in SECTION_LIST:
        content = secs.get(key, "")
        if not content: continue
        with (cl if key in left_k else cr):
            st.subheader(title)
            st.markdown(content)
            st.markdown("")

    with st.expander("GPT 원문 전체 보기"):
        st.text(jt)

st.markdown("---")

# ═════════════════════════════════════════════════════════
# 2. 애널리스트 등급
# ═════════════════════════════════════════════════════════
st.header("📊 애널리스트 등급")

if fmp is None:
    st.warning(f"`output/{symbol}.json` 파일이 없습니다. collect_stock_data_v3.py를 먼저 실행하세요.")
else:
    gc  = safe_get(fmp, "analyst", "grades_consensus")
    ptc = safe_get(fmp, "analyst", "price_target_consensus")
    sg  = safe_get(fmp, "analyst", "stock_grades")

    if gc:
        g = gc[0]
        grades = {
            "Strong Buy":  g.get("strongBuy",  0),
            "Buy":         g.get("buy",         0),
            "Hold":        g.get("hold",        0),
            "Sell":        g.get("sell",        0),
            "Strong Sell": g.get("strongSell",  0),
        }
        total_g = sum(grades.values()) or 1
        GCOL = {
            "Strong Buy":  "#1D9E75", "Buy":  "#26A69A",
            "Hold":        "#888780", "Sell": "#E88B2A",
            "Strong Sell": "#E24B4A",
        }

        # 등급 지표 카드
        cols = st.columns(5)
        for i, (k, v) in enumerate(grades.items()):
            cols[i].metric(k, f"{v}명", f"{v/total_g*100:.0f}%")

        # 가로 막대 차트
        fig_g = go.Figure(go.Bar(
            x=list(grades.values()),
            y=list(grades.keys()),
            orientation="h",
            marker_color=[GCOL[k] for k in grades],
            text=[f"{v}명 ({v/total_g*100:.0f}%)" for v in grades.values()],
            textposition="outside",
        ))
        fig_g.update_layout(
            height=200,
            margin=dict(l=0, r=80, t=10, b=10),
            xaxis_title="애널리스트 수",
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="#000000"),
        )
        fig_g.update_traces(textfont_color="#000000")
        fig_g.update_xaxes(tickfont=dict(color="#000000"), title_font=dict(color="#000000"))
        fig_g.update_yaxes(tickfont=dict(color="#000000"))
        st.plotly_chart(fig_g, use_container_width=True)

    # 최근 등급 변경
    if sg:
        st.markdown("")
        st.markdown("**최근 증권사 등급 변경**")
        df_g = pd.DataFrame(sg)
        if "date" in df_g.columns:
            df_g["date"] = pd.to_datetime(df_g["date"]).dt.strftime("%Y-%m-%d")
        AMAP = {
            "upgrade":    "🟢 상향",
            "downgrade":  "🔴 하향",
            "initiation": "🔵 신규",
            "reiterated": "⚪ 유지",
        }
        if "action" in df_g.columns:
            df_g["action"] = df_g["action"].map(
                lambda x: AMAP.get(str(x).lower(), x)
            )
        show_cols = [c for c in ["date", "gradingCompany", "previousGrade", "newGrade", "action"]
                     if c in df_g.columns]
        st.dataframe(
            df_g[show_cols].rename(columns={
                "date": "날짜", "gradingCompany": "증권사",
                "previousGrade": "이전 등급", "newGrade": "현재 등급", "action": "변경",
            }),
            use_container_width=True,
            hide_index=True,
            height=280,
        )

st.markdown("---")

# ═════════════════════════════════════════════════════════
# 3. 감정 분석
# ═════════════════════════════════════════════════════════
st.header("🧠 감정 분석")

if df_sent is None:
    st.warning(f"`output/{symbol}_sentiment.csv` 파일이 없습니다. investment_analysis.py를 먼저 실행하세요.")
else:
    total  = len(df_sent)
    counts = df_sent["sentiment"].value_counts()

    # 감정 지표 카드
    cols = st.columns(6)
    for i, lb in enumerate(["Growth", "Positive", "Neutral", "Mixed", "Risk", "Negative"]):
        cnt = counts.get(lb, 0)
        cols[i].metric(SENTIMENT_KO[lb], f"{cnt}건", f"{cnt/total*100:.0f}%")

    st.markdown("")

    # 도넛 + 날짜별 바
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        st.markdown("**전체 감정 분포**")
        fig_d = go.Figure(go.Pie(
            labels=[SENTIMENT_KO[l] for l in counts.index],
            values=counts.values,
            hole=0.5,
            marker=dict(colors=[SENTIMENT_COLOR.get(l, "#888") for l in counts.index]),
            textinfo="label+percent",
        ))
        fig_d.update_layout(
            height=300,
            margin=dict(t=10, b=40, l=10, r=10),
            showlegend=True,
            legend=dict(
                orientation="h",
                y=-0.15,
                x=0.5,
                xanchor="center",
                font=dict(color="#ffffff"),
            ),
            font=dict(color="#000000"),
        )
        st.plotly_chart(fig_d, use_container_width=True)

    with sc2:
        st.markdown("**날짜별 감정 흐름**")
        df_sent["date_only"] = df_sent["date"].dt.date
        pivot = df_sent.groupby(["date_only", "sentiment"]).size().reset_index(name="count")
        fig_b = go.Figure()
        for lb in ["Growth", "Positive", "Neutral", "Mixed", "Risk", "Negative"]:
            sub = pivot[pivot["sentiment"] == lb]
            if not sub.empty:
                fig_b.add_trace(go.Bar(
                    x=sub["date_only"], y=sub["count"],
                    name=SENTIMENT_KO[lb],
                    marker_color=SENTIMENT_COLOR[lb],
                ))
        fig_b.update_layout(
            barmode="stack", height=280,
            margin=dict(t=10, b=10, l=0, r=0),
            legend=dict(orientation="h", y=1.15, font=dict(color="#000000")),
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(color="#000000"),
        )
        fig_b.update_xaxes(tickfont=dict(color="#000000"))
        fig_b.update_yaxes(tickfont=dict(color="#000000"))
        st.plotly_chart(fig_b, use_container_width=True)

st.markdown("---")

# ═════════════════════════════════════════════════════════
# 4. 뉴스 목록
# ═════════════════════════════════════════════════════════
st.header("📰 뉴스 목록")

if df_sent is None:
    st.warning("감정 분석 파일이 없어 뉴스 목록을 표시할 수 없습니다.")
else:
    # 필터
    fc1, fc2 = st.columns([2, 1])
    with fc1:
        filter_lb = st.multiselect(
            "감정 필터",
            options=list(SENTIMENT_KO.keys()),
            default=list(SENTIMENT_KO.keys()),
            format_func=lambda x: f"{x} ({SENTIMENT_KO[x]})",
        )
    with fc2:
        sort_order = st.radio("정렬", ["최신순", "오래된순"], horizontal=True)

    df_show = df_sent[df_sent["sentiment"].isin(filter_lb)].copy()
    df_show = df_show.sort_values("date", ascending=(sort_order == "오래된순"))

    st.markdown(f"**총 {len(df_show)}건**")
    st.markdown("")

    for _, row in df_show.iterrows():
        color    = SENTIMENT_COLOR.get(row["sentiment"], "#888")
        label    = SENTIMENT_KO.get(row["sentiment"], row["sentiment"])
        date_str = row["date"].strftime("%Y-%m-%d %H:%M") \
                   if hasattr(row["date"], "strftime") else str(row["date"])
        title = row.get("title_ko") or row.get("title", "제목 없음")
        url      = row.get("url", "")

        col_badge, col_content = st.columns([1, 11])

        with col_badge:
            st.markdown(
                f'<div style="background:{color};color:#fff;'
                f'padding:5px 8px;border-radius:6px;'
                f'font-size:12px;text-align:center;margin-top:6px;'
                f'white-space:nowrap">{label}</div>',
                unsafe_allow_html=True,
            )

        with col_content:
            # 제목에 원문 링크 삽입
            if url:
                st.markdown(
                    f'<a href="{url}" target="_blank" style="font-weight:600;'
                    f'font-size:15px;text-decoration:none;">{title}</a>'
                    f'<br><small style="color:#888">{date_str}</small>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<span style="font-weight:600;font-size:15px">{title}</span>'
                    f'<br><small style="color:#888">{date_str}</small>',
                    unsafe_allow_html=True,
                )

        st.divider()


