"""
주식 투자 분석 대시보드 (리디자인 버전)
구성: 투자 판단 → 애널리스트 등급 → 감정 분석 → 뉴스 목록
실행: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json, os, re, html

# ─────────────────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="주식 투자 분석",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────
# 전역 CSS
# ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&family=Bebas+Neue&display=swap');

/* ── 배경 & 기본 ── */
html, body, [data-testid="stAppViewContainer"] {
    background: #0d0f14 !important;
    color: #dde1ee !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 15px !important;
    line-height: 1.7 !important;
}
[data-testid="stSidebar"] {
    background: #12151d !important;
    border-right: 1px solid #1e2230 !important;
}

/* ── 헤더 폰트 ── */
h1, h2, h3 { font-family: 'DM Sans', sans-serif !important; }

/* ── 메트릭 카드 ── */
[data-testid="stMetric"] {
    background: #161923 !important;
    border: 1px solid #1e2230 !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
}
[data-testid="stMetric"] label {
    color: #8d97b0 !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    color: #f0f2fa !important;
    font-size: 24px !important;
    font-weight: 700 !important;
    font-family: 'DM Mono', monospace !important;
}
[data-testid="stMetricDelta"] {
    font-size: 13px !important;
    font-family: 'DM Mono', monospace !important;
    color: #8d97b0 !important;
}

/* ── 구분선 ── */
hr { border-color: #1e2230 !important; margin: 24px 0 !important; }

/* ── 알림 박스 ── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    font-size: 14px !important;
}

/* ── 데이터프레임 ── */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* ── 셀렉트박스 & 멀티셀렉트 ── */
[data-testid="stSelectbox"] > div,
[data-testid="stMultiSelect"] > div {
    background: #161923 !important;
    border-color: #1e2230 !important;
    border-radius: 8px !important;
    color: #dde1ee !important;
}

/* ── 사이드바 ── */
[data-testid="stSidebar"] * { font-family: 'DM Sans', sans-serif !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {
    color: #8d97b0 !important;
    font-size: 12px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
}

/* ── expander ── */
[data-testid="stExpander"] {
    background: #161923 !important;
    border: 1px solid #1e2230 !important;
    border-radius: 10px !important;
}

/* ── plotly 배경 투명 ── */
.js-plotly-plot { background: transparent !important; }

/* ── 스크롤바 ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d0f14; }
::-webkit-scrollbar-thumb { background: #2a2e3e; border-radius: 3px; }

/* ── 뉴스 카드 애니메이션 ── */
.news-card { animation: fadeSlide 0.3s ease both; }
@keyframes fadeSlide {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── 뉴스 링크 hover ── */
.news-card a:hover {
    color: #00d4a0 !important;
    text-decoration: underline !important;
}

/* ── markdown 본문 가독성 ── */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    font-size: 15px !important;
    line-height: 1.85 !important;
    color: #dde1ee !important;
}
[data-testid="stMarkdownContainer"] strong {
    color: #f0f2fa !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

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
    "Growth":   "#00d4a0", "Positive": "#26A69A", "Neutral":  "#6b7280",
    "Mixed":    "#f59e0b", "Risk":     "#f97316", "Negative": "#ef4444",
}
SENTIMENT_KO = {
    "Growth": "성장 기대", "Positive": "긍정",   "Neutral":  "중립",
    "Mixed":  "혼재",      "Risk":     "리스크",  "Negative": "부정",
}

# ─────────────────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 20px;">
        <div style="font-family:'Bebas Neue',sans-serif; font-size:28px;
                    letter-spacing:0.05em; color:#00d4a0; line-height:1;">
            STOCK<br>INSIGHT
        </div>
        <div style="font-size:11px; color:#5a6480; margin-top:5px;
                    font-weight:500; letter-spacing:0.1em; text-transform:uppercase;">
            투자 분석 대시보드
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:#1e2230;margin-bottom:20px;"></div>', unsafe_allow_html=True)

    model_choice = st.radio(
        "🤖 분석 모델",
        options=["GPT", "Claude"],
        horizontal=True,
    )

    st.markdown('<div style="height:1px;background:#1e2230;margin:20px 0;"></div>', unsafe_allow_html=True)

    sector = st.selectbox("섹터", list(STOCKS.keys()))
    symbol = st.selectbox(
        "종목", STOCKS[sector],
        format_func=lambda s: f"{s}  ·  {COMPANY_NAME.get(s, '')}",
    )

    st.markdown('<div style="height:1px;background:#1e2230;margin:20px 0;"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:12px; color:#5a6480; line-height:1.8;">
        <div style="color:#8d97b0; font-weight:600; margin-bottom:4px;">📡 데이터 소스</div>
        <div>Financial Modeling Prep</div>
        <div>gpt-5.4-mini / gpt-5.4-nano</div>
        <div>Claude</div>
    </div>
    """, unsafe_allow_html=True)

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

fmp          = load_json(os.path.join(OUTPUT_DIR, f"{symbol}.json"))
df_sent      = load_csv(os.path.join(OUTPUT_DIR, f"{symbol}_sentiment.csv"))
model_suffix = "GPT" if model_choice == "GPT" else "claude"
analysis     = load_json(os.path.join(OUTPUT_DIR, f"{symbol}_analysis_{model_suffix}.json"))

# ─────────────────────────────────────────────────────────
# 페이지 헤더
# ─────────────────────────────────────────────────────────
model_badge_color = "#10a37f" if model_choice == "GPT" else "#cc785c"
st.markdown(f"""
<div style="display:flex; align-items:flex-end; gap:16px; padding:8px 0 4px;">
    <div>
        <div style="font-family:'Bebas Neue',sans-serif; font-size:52px;
                    color:#e8eaf0; line-height:1; letter-spacing:0.02em;">
            {symbol}
        </div>
        <div style="font-size:18px; color:#8d97b0; font-weight:400; margin-top:2px;">
            {company}
        </div>
    </div>
    <div style="padding-bottom:12px; display:flex; gap:8px; flex-wrap:wrap;">
        <span style="background:#1e2230; color:#00d4a0; font-size:11px;
                     font-weight:600; padding:4px 12px; border-radius:20px;
                     letter-spacing:0.07em; text-transform:uppercase; border:1px solid #00d4a025;">
            {sector}
        </span>
        <span style="background:#1e2230; color:{model_badge_color}; font-size:11px;
                     font-weight:600; padding:4px 12px; border-radius:20px;
                     letter-spacing:0.07em; text-transform:uppercase; border:1px solid {model_badge_color}25;">
            {model_choice}
        </span>
    </div>
</div>
<div style="height:1px; background:linear-gradient(90deg,#00d4a035,#1e2230 60%); margin:16px 0 28px;"></div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# 헬퍼: 마크다운 → HTML 변환 (HTML 태그 이스케이프 포함)
# ─────────────────────────────────────────────────────────
def md_to_html(text):
    """AI 출력 텍스트의 HTML 태그를 무력화하고 마크다운만 렌더링."""
    # 1) HTML 특수문자 이스케이프 (</div> 등 제거)
    t = html.escape(text)
    # 2) 수평선(---) 제거
    t = re.sub(r'^\s*-{2,}\s*$', '', t, flags=re.MULTILINE)
    # 3) ## 헤딩 제거
    t = re.sub(r'#{1,6}\s*', '', t)
    # 4) 줄 맨 앞의 [섹션명] 헤더 제거 (GPT 원문에 섹션 타이틀이 남아있는 경우)
    t = re.sub(r'^\s*\[.+?\]\s*$', '', t, flags=re.MULTILINE)
    # 5) **bold** / ***bold italic*** 먼저 처리 (순서 중요)
    t = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', t)
    t = re.sub(r'\*\*(.+?)\*\*',     r'<strong>\1</strong>', t)
    # 6) 줄 시작 "* " 불릿 → 들여쓰기 없는 • 항목으로 변환 (이탤릭 오인식 방지)
    t = re.sub(r'^\*{1,2}\s+', '• ', t, flags=re.MULTILINE)
    # 7) 남은 인라인 *이탤릭* 처리
    t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
    # 8) 연속 빈 줄 정리 후 줄바꿈 → <br>
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = t.replace('\n', '<br>')
    return t


# ─────────────────────────────────────────────────────────
# 헬퍼: 섹션 헤더
# ─────────────────────────────────────────────────────────
def section_header(icon, title, subtitle=""):
    sub_html = f'<div style="font-size:13px;color:#6b7a99;margin-top:3px;font-weight:400;">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:14px; margin-bottom:20px;">
        <div style="font-size:24px; line-height:1;">{icon}</div>
        <div>
            <div style="font-size:20px; font-weight:700; color:#e8eaf0;">{title}</div>
            {sub_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# 1. 투자 판단
# ═══════════════════════════════════════════════════════════
section_header("🎯", "투자 판단", "AI 분석 기반 종합 투자 의견")

if analysis is None:
    st.warning(f"`output/{symbol}_analysis_{model_suffix}.json` 파일이 없습니다. 해당 모델 분석 파일을 먼저 실행하세요.")
else:
    meta = analysis.get("meta", {})

    m1, m2, m3 = st.columns(3)
    m1.metric("분석 종목", meta.get("symbol", "-"))
    m2.metric("뉴스 기간", meta.get("news_period", "-"))
    m3.metric("분석 뉴스", f"{meta.get('news_count', 0)}건")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # 투자 판단 배너
    jt = analysis.get("investment_judgment", "")
    verdict_section = ""
    m = re.search(r'\[\s*투자 판단\s*\](.*?)(?=\[|$)', jt, re.DOTALL)
    if m:
        verdict_section = m.group(1)

    if "비투자" in verdict_section:
        verdict_text   = "❌  비투자"
        verdict_bg     = "linear-gradient(135deg, #2d1515, #1a0f0f)"
        verdict_border = "#ef444440"
        verdict_color  = "#ef4444"
    elif "투자" in verdict_section and "비투자" not in verdict_section:
        verdict_text   = "✅  투자"
        verdict_bg     = "linear-gradient(135deg, #0d2018, #091510)"
        verdict_border = "#00d4a040"
        verdict_color  = "#00d4a0"
    else:
        verdict_text   = "⏸️  보류"
        verdict_bg     = "linear-gradient(135deg, #1e1a0d, #151209)"
        verdict_border = "#f59e0b40"
        verdict_color  = "#f59e0b"

    st.markdown(f"""
    <div style="background:{verdict_bg}; border:1px solid {verdict_border};
                border-radius:14px; padding:22px 28px; margin-bottom:24px;
                display:flex; align-items:center; gap:16px;">
        <div style="font-size:26px; font-weight:800; color:{verdict_color};
                    font-family:'DM Mono',monospace; letter-spacing:-0.01em;">
            {verdict_text}
        </div>
        <div style="width:1px; height:32px; background:{verdict_border}; margin:0 4px;"></div>
        <div style="font-size:14px; color:#8d97b0; font-weight:400;">
            {model_choice} 종합 판단 결과
        </div>
    </div>
    """, unsafe_allow_html=True)

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
        for i, key in enumerate(skeys):
            escaped = re.escape(key[1:-1])
            start_match = re.search(rf'\*{{0,2}}\[\s*{escaped}\s*\]\*{{0,2}}', text)
            if not start_match:
                continue
            start = start_match.end()
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
        if not content:
            continue
        target   = cl if key in left_k else cr
        bg_color = "#0d1f18" if "긍정" in title else ("#1f0d0d" if "부정" in title else "#161923")
        border_c = "#00d4a022" if "긍정" in title else ("#ef444422" if "부정" in title else "#1e2230")
        with target:
            st.markdown(f"""
            <div style="background:{bg_color}; border:1px solid {border_c};
                        border-radius:12px; padding:20px 22px; margin-bottom:16px;">
                <div style="font-size:12px; font-weight:700; color:#8d97b0;
                            text-transform:uppercase; letter-spacing:0.07em; margin-bottom:12px;">
                    {title}
                </div>
                <div style="font-size:15px; color:#dde1ee; line-height:1.85;">
                    {md_to_html(content)}
                </div>
            </div>
            """, unsafe_allow_html=True)

    with st.expander(f"📄 {model_choice} 원문 전체 보기"):
        st.code(jt, language=None)

st.markdown("<div style='height:1px;background:#1e2230;margin:24px 0 32px;'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# 2. 애널리스트 등급
# ═══════════════════════════════════════════════════════════
section_header("📊", "애널리스트 등급", "월스트리트 증권사 컨센서스")

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
            "Strong Buy":  "#00d4a0", "Buy":  "#26A69A",
            "Hold":        "#6b7280", "Sell": "#f97316",
            "Strong Sell": "#ef4444",
        }

        cols = st.columns(5)
        for i, (k, v) in enumerate(grades.items()):
            cols[i].metric(k, f"{v}명", f"{v/total_g*100:.0f}%")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        fig_g = go.Figure(go.Bar(
            x=list(grades.values()),
            y=list(grades.keys()),
            orientation="h",
            marker_color=[GCOL[k] for k in grades],
            marker_line_width=0,
            text=[f"{v}명  ({v/total_g*100:.0f}%)" for v in grades.values()],
            textposition="outside",
        ))
        fig_g.update_layout(
            height=210,
            margin=dict(l=0, r=100, t=10, b=10),
            xaxis_title=None,
            plot_bgcolor="#161923",
            paper_bgcolor="#161923",
            font=dict(color="#9aa3b8", family="DM Sans"),
            bargap=0.35,
        )
        fig_g.update_traces(textfont=dict(color="#dde1ee", size=13))
        fig_g.update_xaxes(showgrid=True, gridcolor="#1e2230", zeroline=False, showticklabels=False)
        fig_g.update_yaxes(tickfont=dict(color="#dde1ee", size=13), showgrid=False)

        st.markdown('<div style="background:#161923;border:1px solid #1e2230;border-radius:12px;padding:12px;margin-bottom:20px;">', unsafe_allow_html=True)
        st.plotly_chart(fig_g, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if sg:
        st.markdown("""
        <div style="font-size:13px; font-weight:700; color:#8d97b0;
                    text-transform:uppercase; letter-spacing:0.06em; margin-bottom:12px;">
            최근 증권사 등급 변경
        </div>
        """, unsafe_allow_html=True)
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
            df_g["action"] = df_g["action"].map(lambda x: AMAP.get(str(x).lower(), x))
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

st.markdown("<div style='height:1px;background:#1e2230;margin:24px 0 32px;'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# 3. 감정 분석
# ═══════════════════════════════════════════════════════════
section_header("🧠", "감정 분석", "뉴스 기사 AI 감정 분류 결과")

if df_sent is None:
    st.warning(f"`output/{symbol}_sentiment.csv` 파일이 없습니다. investment_analysis.py를 먼저 실행하세요.")
else:
    total  = len(df_sent)
    counts = df_sent["sentiment"].value_counts()

    # 감정 지표 카드 (6개)
    cols = st.columns(6)
    for i, lb in enumerate(["Growth", "Positive", "Neutral", "Mixed", "Risk", "Negative"]):
        cnt   = counts.get(lb, 0)
        pct   = f"{cnt/total*100:.0f}%" if total else "0%"
        color = SENTIMENT_COLOR[lb]
        with cols[i]:
            st.markdown(f"""
            <div style="background:#161923; border:1px solid #1e2230; border-top:3px solid {color};
                        border-radius:10px; padding:16px; text-align:center;">
                <div style="font-size:12px; color:#8d97b0; font-weight:600;
                            text-transform:uppercase; letter-spacing:0.07em; margin-bottom:10px;">
                    {SENTIMENT_KO[lb]}
                </div>
                <div style="font-size:24px; font-weight:700; color:#f0f2fa;
                            font-family:'DM Mono',monospace;">{cnt}</div>
                <div style="font-size:13px; color:{color}; font-weight:600;
                            font-family:'DM Mono',monospace; margin-top:4px;">{pct}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    sc1, sc2 = st.columns([1, 2])

    with sc1:
        st.markdown("""
        <div style="font-size:12px; font-weight:700; color:#8d97b0;
                    text-transform:uppercase; letter-spacing:0.07em; margin-bottom:8px;">
            전체 감정 분포
        </div>
        """, unsafe_allow_html=True)
        fig_d = go.Figure(go.Pie(
            labels=[SENTIMENT_KO[l] for l in counts.index],
            values=counts.values,
            hole=0.6,
            marker=dict(
                colors=[SENTIMENT_COLOR.get(l, "#888") for l in counts.index],
                line=dict(color="#0d0f14", width=2),
            ),
            textinfo="percent",
            textfont=dict(size=12, color="#e8eaf0"),
        ))
        fig_d.update_layout(
            height=280,
            margin=dict(t=10, b=50, l=10, r=10),
            showlegend=True,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="h", y=-0.18, x=0.5, xanchor="center",
                font=dict(color="#dde1ee", size=12),
            ),
        )
        st.markdown('<div style="background:#161923;border:1px solid #1e2230;border-radius:12px;padding:12px;">', unsafe_allow_html=True)
        st.plotly_chart(fig_d, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with sc2:
        st.markdown("""
        <div style="font-size:12px; font-weight:700; color:#8d97b0;
                    text-transform:uppercase; letter-spacing:0.07em; margin-bottom:8px;">
            날짜별 감정 흐름
        </div>
        """, unsafe_allow_html=True)
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
                    marker_line_width=0,
                ))
        fig_b.update_layout(
            barmode="stack", height=280,
            margin=dict(t=10, b=10, l=0, r=0),
            legend=dict(orientation="h", y=1.12, font=dict(color="#dde1ee", size=12)),
            plot_bgcolor="#161923",
            paper_bgcolor="#161923",
            font=dict(color="#9aa3b8", family="DM Sans"),
            bargap=0.2,
        )
        fig_b.update_xaxes(tickfont=dict(color="#8d97b0", size=12), showgrid=False, zeroline=False, linecolor="#1e2230")
        fig_b.update_yaxes(tickfont=dict(color="#8d97b0", size=12), showgrid=True, gridcolor="#1e2230", zeroline=False)
        st.markdown('<div style="background:#161923;border:1px solid #1e2230;border-radius:12px;padding:12px;">', unsafe_allow_html=True)
        st.plotly_chart(fig_b, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='height:1px;background:#1e2230;margin:24px 0 32px;'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# 4. 뉴스 목록
# ═══════════════════════════════════════════════════════════
section_header("📰", "뉴스 목록", "감정 분류된 최신 뉴스 피드")

if df_sent is None:
    st.warning("감정 분석 파일이 없어 뉴스 목록을 표시할 수 없습니다.")
else:
    fc1, fc2 = st.columns([3, 1])
    with fc1:
        filter_lb = st.multiselect(
            "감정 필터",
            options=list(SENTIMENT_KO.keys()),
            default=list(SENTIMENT_KO.keys()),
            format_func=lambda x: f"{SENTIMENT_KO[x]}  ({x})",
        )
    with fc2:
        sort_order = st.radio("정렬", ["최신순", "오래된순"], horizontal=True)

    df_show = df_sent[df_sent["sentiment"].isin(filter_lb)].copy()
    df_show = df_show.sort_values("date", ascending=(sort_order == "오래된순"))

    st.markdown(f"""
    <div style="font-size:13px; color:#6b7a99; font-weight:500;
                letter-spacing:0.04em; margin-bottom:16px;">
        총 <strong style="color:#dde1ee;">{len(df_show)}건</strong>
    </div>
    """, unsafe_allow_html=True)

    for _, row in df_show.iterrows():
        color    = SENTIMENT_COLOR.get(row["sentiment"], "#888")
        label    = SENTIMENT_KO.get(row["sentiment"], row["sentiment"])
        date_str = row["date"].strftime("%Y.%m.%d  %H:%M") \
                   if hasattr(row["date"], "strftime") else str(row["date"])
        title    = row.get("title_ko") or row.get("title", "제목 없음")
        url      = row.get("url", "")

        title_html = (
            f'<a href="{url}" target="_blank" style="color:#e8edf8; text-decoration:none; '
            f'font-size:15px; font-weight:600; line-height:1.6; display:block;">'
            f'{title}</a>'
        ) if url else (
            f'<span style="color:#e8edf8; font-size:15px; font-weight:600; line-height:1.6;">'
            f'{title}</span>'
        )

        st.markdown(f"""
        <div class="news-card" style="
            background:#161923;
            border:1px solid #1e2230;
            border-left:3px solid {color};
            border-radius:10px;
            padding:16px 20px;
            margin-bottom:10px;
            display:flex;
            align-items:flex-start;
            gap:14px;
        ">
            <div style="flex-shrink:0; margin-top:3px;">
                <div style="background:{color}20; color:{color};
                            font-size:11px; font-weight:700; padding:5px 11px;
                            border-radius:20px; border:1px solid {color}40;
                            letter-spacing:0.05em; white-space:nowrap;">
                    {label}
                </div>
            </div>
            <div style="flex:1; min-width:0;">
                {title_html}
                <div style="font-size:12px; color:#6b7a99; margin-top:7px;
                            font-family:'DM Mono',monospace; letter-spacing:0.02em;">
                    {date_str}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
