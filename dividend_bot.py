import yfinance as yf
import requests
import os
import pandas as pd
from datetime import datetime, timezone

LINE_TOKEN = os.environ.get('LINE_TOKEN')
LINE_USER_ID = os.environ.get('LINE_USER_ID')

# 목표 환율 기준선 (이보다 낮으면 달러 환전 찬스!)
TARGET_EXCHANGE_RATE = 1350.0

# 1. 관리할 종목 리스트 (해외 고배당 + 국내 금융/인프라 통합)
# 국내 주식은 종목코드 뒤에 코스피(.KS) 또는 코스닥(.KQ)을 붙입니다.
TICKERS = {
    'SCHD': '미국 배당성장 ETF',
    'O': '리얼티인컴 (월배당)',
    '105560.KS': 'KB금융 (국내 대표 배당주)',
    '088980.KS': '맥쿼리인프라 (국내 인프라/리츠)'
}

def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    requests.post(url, headers=headers, json=payload)

def get_exchange_rate():
    """원/달러 환율 가져오기"""
    try:
        krw = yf.Ticker("KRW=X")
        current_rate = krw.history(period="1d")['Close'].iloc[-1]
        return current_rate
    except Exception as e:
        print(f"환율 조회 실패: {e}")
        return None

def calculate_rsi(ticker, window=14):
    """최근 3개월 데이터를 바탕으로 14일 RSI(상대강도지수) 계산"""
    try:
        stock = yf.Ticker(ticker)
        # RSI 계산을 위해 3개월치 일봉 데이터 호출
        hist = stock.history(period="3mo")
        if hist.empty:
            return None
        
        delta = hist['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        # 지수이동평균(EMA) 방식의 RSI 계산 (보통 HTS에서 쓰는 방식)
        avg_gain = gain.ewm(com=window-1, min_periods=window).mean()
        avg_loss = loss.ewm(com=window-1, min_periods=window).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except Exception as e:
        print(f"{ticker} RSI 계산 실패: {e}")
        return None

def analyze_portfolio():
    messages = ["🤖 배당주 매수 타이밍 분석 🤖\n"]

    # 1. 환율 체크
    current_rate = get_exchange_rate()
    if current_rate:
        msg = f"💵 현재 원/달러 환율: {current_rate:,.1f}원\n"
        if current_rate <= TARGET_EXCHANGE_RATE:
            msg += f"👉 목표 환율({TARGET_EXCHANGE_RATE}원) 도달! 환전 찬스!\n"
        messages.append(msg + "-" * 20)

    # 2. 개별 종목 분석
    for ticker, name in TICKERS.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            yield_pct = info.get('dividendYield', 0)
            ex_div_timestamp = info.get('exDividendDate')
            
            # 야후 파이낸스에서 국내 주식 배당률이 누락되는 경우를 대비한 방어 로직
            if not yield_pct and info.get('dividendRate') and current_price:
                yield_pct = info.get('dividendRate') / current_price

            # RSI 계산 (30 이하면 과매도/바닥 구간으로 판단)
            rsi = calculate_rsi(ticker)
            
            ex_div_date = datetime.fromtimestamp(ex_div_timestamp, tz=timezone.utc).strftime('%Y-%m-%d') if ex_div_timestamp else "확인불가"
            
            msg_lines = [f"📍 {name} ({ticker})"]
            if current_price:
                msg_lines.append(f"- 현재가: {current_price:,.2f}")
            if yield_pct:
                msg_lines.append(f"- 배당률: {yield_pct * 100:.2f}%")
            msg_lines.append(f"- 배당락: {ex_div_date}")
            
            # RSI 바닥 줍기 알림 로직
            if rsi:
                rsi_msg = f"- RSI(14): {rsi:.1f}"
                if rsi <= 30:
                    rsi_msg += " 🚨 [과매도/바닥권! 줍줍 찬스]"
                msg_lines.append(rsi_msg)
            
            messages.append("\n".join(msg_lines))
            
        except Exception as e:
            print(f"{ticker} 분석 중 에러: {e}")

    final_message = "\n\n".join(messages)
    send_line_message(final_message)
    print("통합 배당주 알림 전송 완료!")

if __name__ == "__main__":
    analyze_portfolio()
