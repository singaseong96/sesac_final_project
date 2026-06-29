# 📊 미국 주식 투자 분석 대시보드

> 뉴스 크롤링 → 번역 → 감정 분석 → 재무 데이터 수집 → **LLM 기반 투자 판단**까지,
> 미국 주요 종목의 투자 의사결정을 돕는 **자동화 파이프라인 + Streamlit 대시보드**입니다.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=Python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=OpenAI&logoColor=white)

---

## 🔍 프로젝트 개요

개인 투자자가 종목을 판단할 때 필요한 **뉴스 흐름·시장 감정·재무 지표·애널리스트 등급**을
한 화면에서 확인할 수 있도록 구성한 프로젝트입니다.
구글 뉴스에서 최신 기사를 수집하고, OpenAI API로 번역·감정 분석한 뒤,
재무 데이터(FMP API)와 결합해 **종목별 투자 판단 결과**를 대시보드로 제공합니다.

분석 대상 종목(섹터별):

| 섹터 | 종목 |
|------|------|
| 테크·AI | NVDA, MSFT, TSM |
| 금융·핀테크 | JPM, V, GS |
| 에너지·원자재 | XOM, CVX |
| 헬스케어·바이오 | ABBV, UNH |

---

## 🔄 데이터 파이프라인

```
[1] news_crawl.py          구글 뉴스 RSS + Selenium 으로 최근 기사 본문 수집
        │
        ▼
[2] translate.py           OpenAI API 로 영문 기사 → 한글 번역 (노이즈 필터링)
        │
        ▼
[3] collect_stock_data.py  FMP API 로 재무지표·애널리스트 등급·목표주가 수집
        │
        ▼
[4] investment_analysis.py OpenAI API 로 뉴스 감정 분석(6개 레이블) + 투자 판단
        │
        ▼
[5] app.py                 Streamlit 대시보드로 결과 시각화
```

**감정 분석 레이블:** `Positive` · `Negative` · `Neutral` · `Growth` · `Risk` · `Mixed`

---

## ✨ 주요 기능

- **뉴스 자동 수집:** 구글 뉴스 RSS + Selenium 기반 최근 기사 본문 크롤링
- **번역 & 감정 분석:** OpenAI API로 한글 번역 후 6개 레이블 감정 분류
- **재무 데이터 통합:** FMP API의 재무지표·애널리스트 등급·목표주가 수집
- **LLM 투자 판단:** 뉴스 + 재무 데이터를 종합한 종목별 투자 의견 생성
- **대시보드 시각화:** 투자 판단 → 애널리스트 등급 → 감정 분석 → 뉴스 목록 구성
- **일일 자동화:** GitHub Actions로 뉴스 크롤링·번역을 매일 자동 실행

---

## 🛠 기술 스택

| 구분 | 사용 기술 |
|------|----------|
| Language | Python |
| 크롤링 | Selenium, BeautifulSoup4, requests |
| LLM | OpenAI API (번역 · 감정 분석 · 투자 판단) |
| 데이터 | Financial Modeling Prep (FMP) API |
| 대시보드 | Streamlit, Plotly |
| 자동화 | GitHub Actions (daily workflow) |

---

## 🚀 실행 방법 (Local)

1. 저장소 클론 및 의존성 설치
   ```bash
   git clone https://github.com/singaseong96/sesac_final_project.git
   cd sesac_final_project
   pip install -r requirements.txt
   ```

2. 환경 변수 설정 — 프로젝트 루트에 `.env` 파일 생성
   ```bash
   OPENAI_API_KEY=your_openai_api_key
   FMP_API_KEY=your_fmp_api_key
   ```
   > `.env`는 `.gitignore`에 포함되어 있어 저장소에 커밋되지 않습니다.

3. 파이프라인 실행
   ```bash
   python news_crawl.py            # 1. 뉴스 수집
   python translate.py             # 2. 번역
   python collect_stock_data.py    # 3. 재무 데이터 수집
   python investment_analysis.py   # 4. 감정 분석 + 투자 판단
   ```

4. 대시보드 실행
   ```bash
   streamlit run app.py
   ```

---

## 📁 프로젝트 구조

```
sesac_final_project/
├── news_crawl.py            # 1. 뉴스 크롤링
├── translate.py             # 2. 번역
├── collect_stock_data.py    # 3. 재무 데이터 수집 (FMP API)
├── investment_analysis.py   # 4. 감정 분석 + 투자 판단 (OpenAI API)
├── app.py                   # 5. Streamlit 대시보드
├── data/                    # 수집·번역된 뉴스 데이터
├── .github/workflows/       # 일일 자동화 워크플로우
├── requirements.txt
└── README.md
```

---

## ⚠️ 참고

- API 키는 모두 환경 변수(`.env` / GitHub Secrets)로 관리하며, 코드에 하드코딩하지 않습니다.
- 크롤링 시점 기준 데이터이므로, 실제 투자 판단의 보조 참고 자료로만 활용하시기 바랍니다.
