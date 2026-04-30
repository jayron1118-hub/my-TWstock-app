import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
from datetime import datetime

# 1. 頁面配置
st.set_page_config(page_title="台股全能轉折預告系統 - 旗艦修復版", layout="wide")

# CSS 樣式
st.markdown("""
    <style>
    .up-p { color: #FF0000; font-size: 42px; font-weight: bold; }
    .down-p { color: #00FF00; font-size: 42px; font-weight: bold; }
    .analysis-box { background-color: #1E222D; padding: 12px; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 10px; }
    .profit-box { background-color: #161A25; padding: 15px; border-radius: 10px; border: 1px solid #00D1FF; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：資料抓取與「欄位標準化」 ---
@st.cache_data(ttl=3600)
def get_stock_data_v3(symbol):
    # 支援代號自動補完
    ticker = f"{symbol}.TW" if symbol.isdigit() else symbol
    
    # 引擎 1: Yahoo Finance (加上抗封鎖偽裝)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False, session=session)
        if df.empty and symbol.isdigit():
            df = yf.download(f"{symbol}.TWO", period="1y", interval="1d", progress=False, session=session)
        
        if not df.empty:
            # 強制處理 MultiIndex 欄位 (yfinance 0.2.x 之後的常見問題)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 強制將欄位名稱轉為首字母大寫，確保 'High', 'Low' 能被找到
            df.columns = [c.capitalize() for c in df.columns]
            return df
    except:
        pass

    # 引擎 2: FinMind 備援
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {"dataset": "TaiwanStockPrice", "data_id": symbol, "start_date": "2024-01-01"}
        res = requests.get(url, params=params).json()
        df_f = pd.DataFrame(res['data'])
        if not df_f.empty:
            df_f = df_f.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'Trading_Volume': 'Volume'})
            df_f['Date'] = pd.to_datetime(df_f['Date'])
            df_f.set_index('Date', inplace=True)
            # 確保欄位標準化
            df_f.columns = [c.capitalize() for c in df_f.columns]
            return df_f
    except:
        pass
    return pd.DataFrame()

# --- 進階分析模組 ---
def perform_analysis(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    # 1. K線形態
    k_msg = "盤整形態"
    if last['Close'] > last['Open'] and last['Close'] > prev['High']: k_msg = "🔥 多頭吞噬 (強勢)"
    elif last['Close'] < last['Open'] and last['Close'] < prev['Low']: k_msg = "📉 黑K吞噬 (轉弱)"
    
    # 2. 123法則：簡單判定
    rule_123 = "趨勢形成中"
    if last['Close'] > df['Ma20'].iloc[-1] and last['Close'] > df['High'].tail(10).max() * 0.98:
        rule_123 = "🎯 123法則：多頭確立"
        
    # 3. 量價背離分析
    div_msg = "✅ 量價配合正常"
    avg_vol = df['Volume'].rolling(5).mean().iloc[-1]
    if last['Close'] > prev['Close'] and last['Volume'] < avg_vol:
        div_msg = "⚠️ 警告：價漲量縮 (動能不足)"
        
    return k_msg, rule_123, div_msg

# --- 側邊欄與獲利計算 ---
st.sidebar.header("🚀 策略監測")
user_input = st.sidebar.text_input("輸入台股代號 (如: 6163)", value="6163")
st.sidebar.markdown("---")
st.sidebar.subheader("💰 個人獲利試算")
my_cost = st.sidebar.number_input("平均持股成本", value=0.0)
my_shares = st.sidebar.number_input("持有股數", value=0, step=1000)

# --- 主程式呈現 ---
try:
    df = get_stock_data_v3(user_input)
    if not df.empty:
        # 計算指標 (注意欄位首字母皆為大寫)
        df['Ma20'] = df['Close'].rolling(20).mean()
        # 未來均線預測
        koudi_20 = df['Close'].iloc[-20]
        ma_future = "上揚" if df['Close'].iloc[-1] > koudi_20 else "下彎"
        
        # MACD 技術分析
        df['Ema12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['Ema26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['Dif'] = df['Ema12'] - df['Ema26']
        df['Dea'] = df['Dif'].ewm(span=9, adjust=False).mean()
        df['Macd_hist'] = df['Dif'] - df['Dea']
        
        # 修正版預告價 (ATR)
        df['Tr'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = df['Tr'].rolling(14).mean().iloc[-1]
        mult = 1.382 if (atr / df['Close'].iloc[-1]) < 0.04 else 0.8
        target_p = df['Close'].iloc[-1] + (df['High'].tail(20).max() - df['Low'].tail(20).min()) * mult

        # 介面顯示
        st.title(f"📈 {user_input} 擬像轉折分析系統")
        now_p = df['Close'].iloc[-1]
        diff = now_p - df['Close'].iloc[-2]
        st.markdown(f"現價：<span class='{'up-p' if diff>=0 else 'down-p'}'>{now_p:.2f}</span>", unsafe_allow_html=True)

        if my_cost > 0 and my_shares > 0:
            profit = (target_p - my_cost) * my_shares
            st.markdown(f"<div class='profit-box'><b>💎 預期獲利：</b> 達標 {target_p:.2f} 時，獲利約 <span style='color:#00D1FF'>$ {profit:,.0f}</span></div>", unsafe_allow_html=True)

        st.divider()

        # 進階診斷看板
        k_m, r1, d_m = perform_analysis(df)
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='analysis-box'><b>K線分析：</b><br>{k_m}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='analysis-box'><b>趨勢評估：</b><br>{r1}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='analysis-box'><b>量價關係：</b><br>{d_m}</div>", unsafe_allow_html=True)

        # 專業圖表
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.4, 0.15, 0.15, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Ma20'], line=dict(color='yellow'), name="月線"), row=1, col=1)
        fig.add_hline(y=target_p, line_dash="dash", line_color="red", row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量"), row=3, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Macd_hist'], marker_color='red', name="MACD柱"), row=4, col=1)
        
        fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        st.info(f"💡 **AI 總結：** 未來均線預測為 **{ma_future}**。預計達成需 **{max(1, round((target_p-now_p)/(atr*0.8)))} 個交易日**。")
    else:
        st.error("❌ 無法取得資料，請檢查代號或是 Yahoo 暫時限流。")
except Exception as e:
    st.error(f"系統錯誤: {e}")
