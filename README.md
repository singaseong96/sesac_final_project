# sesac_final_project
'''
투자 분석용 LLM 평가 최적화 엔드포인트 

[애널리스트] 
<필수> 애널리스트 핵심 의견 
GRADES SUMMARY - 종목별 BUY/HOLD/SELL 집계수
PRICE TARGET CONSENSUS - 컨센서스 목표주가. 현재가 대비 업사이드/다운사이드 계산 바로 사용 가능. 
FINANCIAL ESTIMATES - 향후 1~3년 매출, EPS, EBITDA 애널리스트 추정치, 성장 기대값을 LLM 직접 제공 
<권장> 등급 히스토리
Grade Summary - 종목별 buy/hold/sell 집계수
Price Target Consensus - 컨센서스 목표주가
financial estimates - 향후 1~3년 매출, EPS, EBITDA 애널리스트 추정치
[펀더맨털]
<필수> 핵심 재무 지표 TTM 
KEY METRICS TTM - 핵심 밸류에이션 지표
FINANCIAL RATIOS TTM - 기업 건전성 판단용

[밸류에이션]
<필수> 평가 점수 및 내재가치 
RATINGS SNAPSHOT - FMP 자체 종합 점수 
FINANCIAL SCORES 
DCF VALUATION 

[뉴스 센티먼트]
<권장>
STOCK NEWS 
INSIDER TRADE STATISTICS
EARNINGS TRANSCRIPT

[시장 맥락]
<권장> 시장 섹터 저장 
SECTOR PE SNAPSHOT
TREASURY RATES
EARNINGS REPORT 
'''
