import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
import time
from datetime import datetime

# 1. 頁面配置與專業深色介面
st.set_page_config(page_title="台股全能轉折預告系統 - 擬像超越旗艦版", layout="wide")

st.markdown("""
    <style>
    .up-p { color: #FF0000; font-size: 42px; font-weight: bold; }
    .down-p { color: #00FF00; font-size: 42px; font-weight: bold; }
    .analysis-box { background-color: #1E222D; padding: 12px; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 10px; }
    .profit-box { background-color: #161A25; padding: 15px; border-radius: 10px; border: 1px solid #00D1FF; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：修正後的資料抓取與「強制欄位對齊」 ---
@st.cache_data(ttl=600)
def get_clean_data(user_input):
    # 支援代號自動補完與繁體中文搜尋
    symbol = user_input.strip()
    ticker = f"{symbol}.TW" if symbol.isdigit() else symbol
    
    # 建立偽裝 Session
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    df = pd.DataFrame()
    try:
        # 嘗試從 Yahoo 下載
        df = yf.download(ticker, period="1y", interval="1d", progress=False, session=session)
        if df.empty and symbol.isdigit():
            df = yf.download(f"{symbol}.TWO", period="1y", interval="1d", progress=False, session=session)
            
        if not df.empty:
            # 【關鍵修復 1】抹平 MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 【關鍵修復 2】強制標準化欄位名稱：首字母大寫，其餘小寫
            df.columns = [str(c).capitalize() for c in df.columns]
            
            # 確保索引是日期格式
            df.index = pd.to_datetime(df.index)
            return df
    except:
        pass
        
    # 備援引擎：FinMind
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {"dataset": "TaiwanStockPrice", "data_id": symbol, "start_date": "2024-01-01"}
        res = requests.get(url, params=params).json()
        df_f = pd.DataFrame(res['data'])
        if not df_f.empty:
            df_f = df_f.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'Trading_Volume': 'Volume'})
            df_f['Date'] = pd.to_datetime(df_f['Date'])
            df_f.set_index('Date', inplace=True)
            df_f.columns = [str(c).capitalize() for c in df_f.columns]
            return df_f
    except:
        pass
    return pd.DataFrame()

# --- 技術診斷模組 ---
def perform_diagnostic(df):
    last, prev = df.iloc[-1], df.iloc[-2]
    # 1. K線分析
    k_msg = "盤整中"
    if last['Close'] > last['Open'] and last['Close'] > prev['High']: k_msg = "🔥 多頭吞噬"
    elif last['Close'] < last['Open'] and last['Close'] < prev['Low']: k_msg = "📉 空頭吞噬"
    
    # 2. 123法則
    r123 = "趨勢形成中"
    if last['Close'] > df['Ma20'].iloc[-1] and last['Close'] > df['High'].tail(10).max() * 0.99:
        r123 = "🎯 123法則：多頭確認"
    
    # 3. 量價背離
    avg_vol = df['Volume'].rolling(5).mean().iloc[-1]
    div_msg = "✅ 量價配合"
    if last['Close'] > prev['Close'] and last['Volume'] < avg_vol:
        div_msg = "⚠️ 警告：價漲量縮"
    
    return k_msg, r123, div_msg

# --- 側邊欄 ---
st.sidebar.header("🚀 系統監測")
search_id = st.sidebar.text_input("代號或中文 (如: 6163)", value="6163")
st.sidebar.markdown("---")
st.sidebar.subheader("💰 獲利試算器")
cost = st.sidebar.number_input("平均持股成本", value=0.0)
qty = st.sidebar.number_input("持有股數", value=0, step=1000)

# --- 主畫面 ---
try:
    df = get_clean_data(search_id)
    if not df.empty:
        # 計算核心指標
        df['Ma20'] = df['Close'].rolling(20).mean()
        # 未來均線預測 (扣抵)
        deduct_20 = df['Close'].iloc[-20]
        ma_future = "上揚" if df['Close'].iloc[-1] > deduct_20 else "下彎"
        
        # MACD
        df['Ema12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['Ema26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['Dif'] = df['Ema12'] - df['Ema26']
        df['Dea'] = df['Dif'].ewm(span=9, adjust=False).mean()
        df['Macd_hist'] = df['Dif'] - df['Dea']
        
        # 修正後的預告價邏輯
        df['Tr'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = df['Tr'].rolling(14).mean().iloc[-1]
        mult = 1.382 if (atr / df['Close'].iloc[-1]) < 0.04 else 0.8
        target_p = df['Close'].iloc[-1] + (df['High'].tail(20).max() - df['Low'].tail(20).min()) * mult

        st.title(f"🚀 {search_id} 專業決策儀表板")
        now_p = df['Close'].iloc[-1]
        st.markdown(f"現價：<span class='{'up-p' if now_p >= df['Close'].iloc[-2] else 'down-p'}'>{now_p:.2f}</span>", unsafe_allow_html=True)

        if cost > 0 and qty > 0:
            exp_p = (target_p - cost) * qty
            st.markdown(f"<div class='profit-box'><b>💎 預期獲利：</b> 達標 {target_p:.2f} 時，獲利約 <span style='color:#00D1FF'>$ {exp_p:,.0f}</span></div>", unsafe_allow_html=True)

        st.divider()
        k_m, r1, d_m = perform_diagnostic(df)
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='analysis-box'><b>K線：</b>{k_m}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='analysis-box'><b>形態：</b>{r1}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='analysis-box'><b>量價：</b>{d_m}</div>", unsafe_allow_html=True)

        # 圖表製作
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.4, 0.15, 0.15, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Ma20'], line=dict(color='yellow'), name="月線"), row=1, col=1)
        fig.add_hline(y=target_p, line_dash="dash", line_color="red", row=1, col=1)
        
        # 加上成交量與 MACD
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量"), row=3, col=1)
        m_colors = ['red' if v >= 0 else 'green' for v in df['Macd_hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['Macd_hist'], marker_color=m_colors, name="MACD柱"), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Dif'], line=dict(color='white'), name="DIF"), row=4, col=1)
        
        fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        st.info(f"💡 **AI 策略：** 預計達成需 **{max(1, round((target_p-now_p)/(atr*0.8)))} 個交易日**。月線預期將 **{ma_future}**。")
    else:
        st.error("❌ 抓不到資料，請嘗試『Reboot App』或更換代號。")
except Exception as e:
    st.error(f"系統錯誤: {e}")
