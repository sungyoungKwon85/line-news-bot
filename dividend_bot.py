import argparse
import os
from datetime import datetime

import yfinance as yf


LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

TARGET_EXCHANGE_RATE = 1350.0
MAX_CANDIDATES = 3

FX_TICKERS = {
    "USD/KRW": "KRW=X",
    "EUR/KRW": "EURKRW=X",
    "GBP/KRW": "GBPKRW=X",
}

THEME_BASKETS = {
    "AI/반도체": {
        "NVDA": "엔비디아",
        "AMD": "AMD",
        "SMH": "반도체 ETF",
        "SOXX": "반도체 ETF",
        "005930.KS": "삼성전자",
        "000660.KS": "SK하이닉스",
    },
    "로봇/피지컬AI": {
        "BOTZ": "로봇/AI ETF",
        "ROBO": "로봇 ETF",
        "IRBO": "AI/로봇 ETF",
    },
    "소프트웨어/AI인프라": {
        "MSFT": "마이크로소프트",
        "PLTR": "팔란티어",
        "NOW": "서비스나우",
        "IGV": "소프트웨어 ETF",
    },
    "전력기기/전력인프라": {
        "GRID": "스마트그리드 ETF",
        "ETN": "이튼",
        "GEV": "GE 버노바",
    },
    "바이오/헬스케어": {
        "IBB": "바이오 ETF",
        "XBI": "바이오 ETF",
        "LLY": "일라이릴리",
    },
    "방산/우주": {
        "ITA": "방산 ETF",
        "PPA": "방산 ETF",
        "LMT": "록히드마틴",
        "012450.KS": "한화에어로스페이스",
        "079550.KS": "LIG넥스원",
        "064350.KS": "현대로템",
    },
    "조선/산업재": {
        "329180.KS": "HD현대중공업",
        "009540.KS": "HD한국조선해양",
        "010140.KS": "삼성중공업",
        "042660.KS": "한화오션",
    },
}

INCOME_WATCHLIST = {
    "SCHD": "미국 배당성장 ETF",
    "DGRO": "미국 배당성장 ETF",
    "VYM": "미국 고배당 ETF",
    "JEPI": "미국 월분배 인컴 ETF",
    "088980.KS": "맥쿼리인프라",
}

COMPANY_NOTES = {
    "NVDA": "AI GPU와 데이터센터 반도체 대표주",
    "AMD": "CPU/GPU와 AI 가속기 경쟁주",
    "SMH": "미국 상장 반도체 대표 ETF",
    "SOXX": "미국 반도체 업종 ETF",
    "005930.KS": "메모리와 파운드리 중심의 한국 대표 반도체",
    "000660.KS": "HBM과 메모리 중심의 반도체 대표주",
    "BOTZ": "로봇/자동화 관련 글로벌 ETF",
    "ROBO": "로봇과 자동화 기업 분산 ETF",
    "IRBO": "AI와 로봇 관련 기업 ETF",
    "MSFT": "클라우드와 기업용 AI 소프트웨어",
    "PLTR": "데이터 분석과 AI 플랫폼",
    "NOW": "기업 업무 자동화와 AI 소프트웨어",
    "IGV": "북미 소프트웨어 기업 ETF",
    "GRID": "스마트그리드와 전력 인프라 ETF",
    "ETN": "전력관리 장비, 데이터센터 전력 인프라 수혜",
    "GEV": "전력설비, 가스터빈, 전력망 인프라",
    "IBB": "대형 바이오 기업 ETF",
    "XBI": "중소형 바이오 성장주 ETF",
    "LLY": "비만치료제와 당뇨 치료제 중심 제약사",
    "ITA": "미국 방산/항공 ETF",
    "PPA": "미국 방산/항공우주 ETF",
    "LMT": "록히드마틴, 미국 대형 방산주",
    "012450.KS": "한화에어로스페이스, 항공엔진/방산/우주",
    "079550.KS": "LIG넥스원, 유도무기/방공/방산 전자",
    "064350.KS": "현대로템, 방산 지상무기와 철도",
    "329180.KS": "HD현대중공업, 조선/해양플랜트",
    "009540.KS": "HD한국조선해양, 조선 지주 성격",
    "010140.KS": "삼성중공업, LNG선/해양플랜트",
    "042660.KS": "한화오션, 방산과 조선 복합 노출",
}

INCOME_PROFILES = {
    "SCHD": {
        "min_yield": 3.0,
        "note": "배당성장 ETF 정상 범위",
        "low_yield_note": "배당성장 ETF치고 배당률 확인 필요",
    },
    "DGRO": {
        "min_yield": 1.8,
        "note": "배당률보다 배당성장/퀄리티 성격",
        "low_yield_note": "배당률은 낮지만 성장/퀄리티 성격",
    },
    "VYM": {
        "min_yield": 3.0,
        "note": "고배당 ETF 배당 매력 확인",
        "low_yield_note": "고배당 ETF치고 배당 매력은 약함",
    },
    "JEPI": {
        "min_yield": 6.0,
        "note": "고분배 상품, 커버드콜 특성 확인",
        "low_yield_note": "고분배 ETF치고 분배 매력 확인 필요",
    },
    "088980.KS": {
        "min_yield": 5.0,
        "note": "국내 인프라 인컴 성격",
        "low_yield_note": "배당은 토스/공시 확인 필요",
    },
}


def send_line_message(text):
    import requests

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}",
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    response.raise_for_status()


def get_exchange_rates():
    rates = {}
    for label, ticker in FX_TICKERS.items():
        rates[label] = get_exchange_rate(label, ticker)
    return rates


def get_exchange_rate(label, ticker):
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as exc:
        print(f"{label} 환율 조회 실패: {exc}")
        return None


def calculate_rsi(close, window=14):
    if close.empty or len(close) < window + 1:
        return None

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()

    if avg_loss.iloc[-1] == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def pct_change(close, periods):
    if close.empty or len(close) <= periods:
        return None

    before = close.iloc[-periods - 1]
    after = close.iloc[-1]
    if before == 0:
        return None
    return float((after / before - 1) * 100)


def moving_average_gap(close, window):
    if close.empty or len(close) < window:
        return None

    ma = close.rolling(window).mean().iloc[-1]
    if ma == 0:
        return None
    return float((close.iloc[-1] / ma - 1) * 100)


def analyze_ticker(ticker, name, theme=None):
    try:
        hist = yf.Ticker(ticker).history(period="3mo", auto_adjust=False)
        if hist.empty:
            print(f"{ticker} 가격 데이터 없음")
            return None

        close = hist["Close"].dropna()
        if close.empty:
            print(f"{ticker} 종가 데이터 없음")
            return None

        return {
            "ticker": ticker,
            "name": name,
            "theme": theme,
            "price": float(close.iloc[-1]),
            "day_return": pct_change(close, 1),
            "five_day_return": pct_change(close, 5),
            "twenty_day_return": pct_change(close, 20),
            "rsi": calculate_rsi(close),
            "ma20_gap": moving_average_gap(close, 20),
            "ma60_gap": moving_average_gap(close, 60),
        }
    except Exception as exc:
        print(f"{ticker} 분석 실패: {exc}")
        return None


def analyze_income_ticker(ticker, name):
    data = analyze_ticker(ticker, name)
    if not data:
        return None

    try:
        info = yf.Ticker(ticker).info
        dividend_yield = info.get("dividendYield")
        dividend_rate = info.get("dividendRate")
        if not dividend_yield and dividend_rate and data["price"]:
            dividend_yield = dividend_rate / data["price"]
        if dividend_yield:
            dividend_yield = float(dividend_yield)
            data["dividend_yield"] = (
                dividend_yield if dividend_yield > 1 else dividend_yield * 100
            )
        else:
            data["dividend_yield"] = None
    except Exception as exc:
        print(f"{ticker} 배당 정보 조회 실패: {exc}")
        data["dividend_yield"] = None

    return data


def pick_theme_movers(results):
    day_sorted = sorted(
        [item for item in results if item["day_return"] is not None],
        key=lambda item: item["day_return"],
        reverse=True,
    )
    movers = day_sorted[:2]

    five_day_sorted = sorted(
        [item for item in results if item["five_day_return"] is not None],
        key=lambda item: item["five_day_return"],
        reverse=True,
    )
    for item in five_day_sorted:
        if item["ticker"] not in {mover["ticker"] for mover in movers}:
            movers.append(item)
            break

    return movers[:3]


def analyze_themes():
    ticker_results = []
    theme_results = []

    for theme, tickers in THEME_BASKETS.items():
        results = []
        for ticker, name in tickers.items():
            result = analyze_ticker(ticker, name, theme)
            if result:
                results.append(result)
                ticker_results.append(result)

        valid_day_returns = [
            item["day_return"] for item in results if item["day_return"] is not None
        ]
        valid_five_day_returns = [
            item["five_day_return"]
            for item in results
            if item["five_day_return"] is not None
        ]

        if not valid_day_returns:
            continue

        avg_day = sum(valid_day_returns) / len(valid_day_returns)
        avg_five = (
            sum(valid_five_day_returns) / len(valid_five_day_returns)
            if valid_five_day_returns
            else None
        )
        participation = (
            sum(1 for value in valid_day_returns if value > 0)
            / len(valid_day_returns)
            * 100
        )

        score = 0
        if avg_day > 0:
            score += 1
        if avg_five is not None and avg_five > 0:
            score += 1
        if participation >= 50:
            score += 1

        theme_results.append(
            {
                "theme": theme,
                "avg_day": avg_day,
                "avg_five": avg_five,
                "participation": participation,
                "score": score,
                "overheated": avg_day >= 3,
                "movers": pick_theme_movers(results),
            }
        )

    theme_results.sort(
        key=lambda item: (item["score"], item["avg_day"]), reverse=True
    )
    return theme_results, ticker_results


def score_candidate(item, theme_scores):
    score = 0
    warnings = []
    reasons = []

    theme_score = theme_scores.get(item["theme"], 0)
    if theme_score >= 2:
        score += 1
        reasons.append("강한 테마 안에 있음")

    ma20_gap = item["ma20_gap"]
    if ma20_gap is not None and -3 <= ma20_gap <= 1:
        score += 1
        if ma20_gap < 0:
            reasons.append(
                f"20일선보다 {abs(ma20_gap):.1f}% 낮아 가격 부담이 덜함"
            )
        elif ma20_gap > 0:
            reasons.append(f"20일선보다 {ma20_gap:.1f}% 높지만 근처에 있음")
        else:
            reasons.append("20일선 바로 근처에 있음")

    rsi = item["rsi"]
    if rsi is not None and 40 <= rsi <= 55:
        score += 1
        reasons.append(f"RSI {format_number(rsi)}로 과열권이 아님")

    day_return = item["day_return"]
    if day_return is not None and day_return >= 3:
        score -= 1
        warnings.append(f"전일 {format_percent(day_return)} 올라 바로 따라가기 부담")

    five_day_return = item["five_day_return"]
    if five_day_return is not None and five_day_return >= 10:
        score -= 1
        warnings.append(f"5일 {format_percent(five_day_return)} 올라 단기 과열 부담")

    if warnings:
        label = "추격 주의"
    elif score >= 2:
        label = "쉬어가는 후보"
    elif score == 1:
        label = "관심 후보"
    else:
        label = "관망"

    return score, label, warnings, reasons


def pick_candidates(ticker_results, theme_results):
    theme_scores = {item["theme"]: item["score"] for item in theme_results}
    candidates = []

    for item in ticker_results:
        score, label, warnings, reasons = score_candidate(item, theme_scores)
        if label == "관망":
            continue

        candidates.append(
            {
                **item,
                "score": score,
                "label": label,
                "warnings": warnings,
                "reasons": reasons,
            }
        )

    label_priority = {"쉬어가는 후보": 3, "관심 후보": 2, "추격 주의": 1}
    candidates.sort(
        key=lambda item: (
            label_priority.get(item["label"], 0),
            item["score"],
            item["day_return"] if item["day_return"] is not None else -100,
        ),
        reverse=True,
    )
    return candidates[:MAX_CANDIDATES]


def format_percent(value, digits=1):
    if value is None:
        return "N/A"
    return f"{value:+.{digits}f}%"


def format_number(value, digits=1):
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def format_mover(item):
    return f"{item['name']} {format_percent(item['day_return'])}"


def format_theme_line(theme):
    five_day = format_percent(theme["avg_five"])
    hot_mark = " / 과열주의" if theme["overheated"] else ""
    breadth = "바스켓 전반 상승" if theme["participation"] >= 75 else "일부 종목 중심"
    movers = ", ".join(format_mover(item) for item in theme.get("movers", []))
    lines = [
        (
            f"- {theme['theme']}: 전일 {format_percent(theme['avg_day'])}, "
            f"5일 {five_day}, 상승비율 {theme['participation']:.0f}% "
            f"({breadth}){hot_mark}"
        )
    ]
    if movers:
        lines.append(f"  대표 움직임: {movers}")
    return "\n".join(lines)


def format_candidate_line(item):
    note = COMPANY_NOTES.get(item["ticker"], "테마 대표 종목/ETF")
    reasons = ", ".join(item["reasons"]) if item["reasons"] else "조건 일부 충족"
    warning = f", 단 {' / '.join(item['warnings'])}" if item["warnings"] else ""
    return "\n".join(
        [
            f"- {item['label']} | {item['name']}({item['ticker']}): {note}",
            (
                f"  이유: {reasons}; 전일 {format_percent(item['day_return'])}, "
                f"5일 {format_percent(item['five_day_return'])}{warning}"
            ),
        ]
    )


def score_income_item(item, usd_krw):
    score = 0
    reasons = []
    profile = INCOME_PROFILES.get(item["ticker"], {})
    min_yield = profile.get("min_yield")
    dividend_yield = item.get("dividend_yield")

    if min_yield is not None and dividend_yield is not None:
        if dividend_yield >= min_yield:
            score += 1
            reasons.append(profile.get("note", "배당률 기준 충족"))
        else:
            reasons.append(profile.get("low_yield_note", "배당률 기준 미달"))
    elif dividend_yield is None:
        reasons.append("배당률 확인 필요")

    rsi = item.get("rsi")
    if rsi is not None and 35 <= rsi <= 55:
        score += 1
        reasons.append(f"RSI {format_number(rsi)}")

    ma20_gap = item.get("ma20_gap")
    if ma20_gap is not None and -5 <= ma20_gap <= 1:
        score += 1
        reasons.append(f"20일선 {format_percent(ma20_gap)}")

    five_day_return = item.get("five_day_return")
    if five_day_return is not None and five_day_return < 5:
        score += 1
        reasons.append("가격 과열 아님")

    is_us_ticker = ".KS" not in item["ticker"] and ".KQ" not in item["ticker"]
    if is_us_ticker:
        if usd_krw and usd_krw <= TARGET_EXCHANGE_RATE:
            score += 1
            reasons.append("환율 부담 낮음")
        else:
            reasons.append("환율 부담 큼")
    else:
        score += 1
        reasons.append("원화 자산")

    return min(score, 5), reasons


def format_income_line(item):
    dividend = (
        f"{item['dividend_yield']:.2f}%"
        if item.get("dividend_yield") is not None
        else "N/A"
    )
    score = item.get("income_score", 0)
    reasons = " + ".join(item.get("income_reasons", [])) or "근거 부족"
    return "\n".join(
        [
            f"- {item['name']}({item['ticker']}): 배당 {dividend}, 배당점수 {score}/5",
            f"  근거: {reasons}",
        ]
    )


def build_tone(theme_results, candidates, usd_krw):
    if not theme_results:
        return "데이터 부족. 새 후보보다 관망 우선."

    strong_themes = "/".join(item["theme"].split("/")[0] for item in theme_results[:2])
    tone_parts = [f"{strong_themes} 강세"]

    if usd_krw and usd_krw > TARGET_EXCHANGE_RATE:
        tone_parts.append("환율 부담 큼")

    if any(item["label"] == "쉬어가는 후보" for item in candidates):
        tone_parts.append("추격보다 쉬어가는 구간 확인")
    elif any(item["label"] == "추격 주의" for item in candidates):
        tone_parts.append("후보는 있으나 추격 주의")
    else:
        tone_parts.append("뚜렷한 쉬어가는 후보 적음")

    return ". ".join(tone_parts) + "."


def build_report():
    exchange_rates = get_exchange_rates()
    usd_krw = exchange_rates.get("USD/KRW")
    theme_results, ticker_results = analyze_themes()
    candidates = pick_candidates(ticker_results, theme_results)

    income_results = []
    for ticker, name in INCOME_WATCHLIST.items():
        result = analyze_income_ticker(ticker, name)
        if result:
            score, reasons = score_income_item(result, usd_krw)
            result["income_score"] = score
            result["income_reasons"] = reasons
            income_results.append(result)

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"📈 데일리 주식 기회 리포트 ({today})"]

    fx_parts = [
        f"{label} {rate:,.1f}원"
        for label, rate in exchange_rates.items()
        if rate is not None
    ]
    if fx_parts:
        fx_msg = " / ".join(fx_parts)
        if usd_krw and usd_krw > TARGET_EXCHANGE_RATE:
            fx_msg += " / 미국주식 환율 부담"
        else:
            fx_msg += " / 환율 부담 완화"
        lines.append(fx_msg)
    else:
        lines.append("환율 조회 실패")

    lines.append(f"📌 오늘 톤: {build_tone(theme_results, candidates, usd_krw)}")

    lines.append("")
    lines.append("🔥 강한 성장 테마")
    if theme_results:
        for theme in theme_results[:3]:
            lines.append(format_theme_line(theme))
    else:
        lines.append("- 테마 데이터 부족")

    lines.append("")
    lines.append("🎯 오늘 볼 후보")
    if candidates:
        for candidate in candidates:
            lines.append(format_candidate_line(candidate))
    else:
        lines.append("- 뚜렷한 쉬어가는 후보 없음. 추격보다 관망 우선.")

    lines.append("")
    lines.append("💰 배당/인컴 보조 체크")
    if income_results:
        for item in income_results:
            lines.append(format_income_line(item))
    else:
        lines.append("- 배당/인컴 데이터 부족")

    lines.append("")
    lines.append("⚠️ 리스크 메모")
    if usd_krw and usd_krw > TARGET_EXCHANGE_RATE:
        lines.append("- 환율이 기준선보다 높아 미국 종목은 분할 접근 우선.")
    if candidates:
        if usd_krw and usd_krw > TARGET_EXCHANGE_RATE and all(
            ".KS" not in item["ticker"] and ".KQ" not in item["ticker"]
            for item in candidates
        ):
            lines.append("- 오늘 후보가 모두 미국 종목. 원화 기준 매수 부담 큼.")
        top_themes = {item["theme"] for item in candidates}
        if len(top_themes) == 1:
            lines.append("- 후보가 한 테마에 몰림. 섹터 쏠림 주의.")
    if any(item["overheated"] for item in theme_results[:3]):
        lines.append("- 상위 테마 중 전일 급등 테마 있음. 추격매수 주의.")
    lines.append("- 현금 여력이 크지 않으면 후보 확인과 분할 접근을 우선.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="LINE daily stock opportunity report")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report without sending a LINE message.",
    )
    args = parser.parse_args()

    report = build_report()
    if args.dry_run:
        print(report)
        return

    if not LINE_TOKEN or not LINE_USER_ID:
        raise RuntimeError("LINE_TOKEN and LINE_USER_ID must be set.")

    send_line_message(report)
    print("데일리 주식 기회 리포트 전송 완료!")


if __name__ == "__main__":
    main()
