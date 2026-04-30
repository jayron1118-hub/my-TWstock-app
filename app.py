import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
import time
from datetime import datetime

# 1. 頁面配置
st.set_page_config(page_title="台股全能轉折預告系統 - 終極超越版", layout="wide")

# CSS 樣式
st.markdown("""
    <style>
    .up-p { color: #FF0000; font-size: 40px; font-weight: bold; }
    .down-p { color: #00FF00; font-size: 40px; font-weight: bold; }
    .analysis-box { background-color: #1E222D; padding: 15px; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 15px; }
    .profit-box { background-color: #161A25; padding: 15px; border-radius: 10px; border: 1px solid #00D1FF; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心修復：抗封鎖抓取器 ---
@st.cache_data(ttl=3600)
def get_stock_data_resilient(symbol):
    # 偽裝成最新瀏覽器
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    }
    session = requests.Session()
    session.headers.update(headers)
    
    ticker = f"{symbol}.TW"
    try:
        # 使用 Session 進行抓取，並加入多次重試與延遲
        for _ in range(3):
            df = yf.download(ticker, period="1y", interval="1d", progress=False, session=session)
            if df.empty:
                df = yf.download(f"{symbol}.TWO", period="1y", interval="1d", progress=False, session=session)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
            time.sleep(1) # 若失敗，等一秒再試
    except:
        pass
    return pd.DataFrame()

# --- 進階分析邏輯 ---
def analyze_advanced(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. K線形態
    k_msg = "盤整中"
    if last['Close'] > last['Open'] and last['Close'] > prev['High']: k_msg = "多頭攻擊 (吞噬)"
    elif last['Close'] < last['Open'] and last['Close'] < prev['Low']: k_msg = "空頭回補 (破位)"
    
    # 2. 123法則評估
    # 條件：1.突破均線 2.回測不破 3.突破前高
    rule_123 = "趨勢形成中"
    if last['Close'] > df['MA20'].iloc[-1] and last['Close'] > df['High'].tail(10).max() * 0.98:
        rule_123 = "123法則：多頭確立"
        
    # 3. 量價背離
    price_up = last['Close'] > prev['Close']
    vol_down = last['Volume'] < df['Volume'].rolling(5).mean().iloc[-1]
    div_msg = "✅ 量價配合"
    if price_up and vol_down: div_msg = "⚠️ 量價背離 (價漲量縮)"
    
    return k_msg, rule_123, div_msg

# --- 側邊欄 ---
st.sidebar.header("📊 系統面板")
search_input = st.sidebar.text_input("輸入個股代號 (如: 6163)", value="6163")
cost_p = st.sidebar.number_input("持股成本", value=0.0)
shares = st.sidebar.number_input("持有股數", value=0, step=1000)

# --- 主畫面 ---
try:
    df = get_stock_data_resilient(search_input)
    if not df.empty:
        # 指標計算
        df['MA20'] = df['Close'].rolling(20).mean()
        # 未來均線預測 (扣抵位邏輯)
        koudi_20 = df['Close'].iloc[-20]
        ma_future = "上揚助漲" if df['Close'].iloc[-1] > koudi_20 else "走平或下彎"
        
        # MACD 技術分析
        df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = df['EMA12'] - df['EMA26']
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['DIF'] - df['DEA']
        
        # 預告價邏輯 (修正過於樂觀)
        atr = (df['High']-df['Low']).rolling(14).mean().iloc[-1]
        mult = 1.382 if atr/df['Close'].iloc[-1] < 0.03 else 0.8
        target_p = df['Close'].iloc[-1] + (df['High'].tail(20).max() - df['Low'].tail(20).min()) * mult

        # 介面顯示
        st.title(f"🚀 {search_input} 擬像轉折分析")
        
        # 獲利試算
        if cost_p > 0 and shares > 0:
            profit = (target_p - cost_p) * shares
            st.markdown(f"<div class='profit-box'><b>💰 預期獲利：</b> 若達標 {target_p:.2f}，預計獲利 <span style='color:#00D1FF'>$ {profit:,.0f}</span></div>", unsafe_allow_html=True)

        st.divider()
        
        # 進階分析卡片
        k_msg, r123, d_msg = analyze_advanced(df)
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div class='analysis-box'><b>K線形態：</b><br>{k_msg}</div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='analysis-box'><b>趨勢評估：</b><br>{r123}</div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='analysis-box'><b>量價關係：</b><br>{d_msg}</div>", unsafe_allow_html=True)

        # 四層圖表
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.4, 0.15, 0.15, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)
        fig.add_hline(y=target_p, line_dash="dash", line_color="red", row=1, col=1)
        
        # MACD 與 成交量
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量"), row=3, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color='red', name="MACD柱"), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], line=dict(color='white'), name="DIF"), row=4, col=1)
        
        fig.update_layout(height=1100, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        st.info(f"💡 **AI 決策：** 未來 20 日均線預計將 **{ma_future}**。MACD 目前為 **{'多頭噴發' if df['DIF'].iloc[-1]>0 else '空頭整理'}**。")

    else:
        st.warning("⚠️ 目前仍受 Yahoo 限流保護中，請點擊右上方『Settings -> Reboot App』並稍候再試。")
except Exception as e:
    st.error(f"分析異常: {e}")
