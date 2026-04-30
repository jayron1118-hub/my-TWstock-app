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
st.set_page_config(page_title="台股全能轉折預告系統 - 終極備援版", layout="wide")

st.markdown("""
    <style>
    .up-p { color: #FF0000; font-size: 40px; font-weight: bold; }
    .down-p { color: #00FF00; font-size: 40px; font-weight: bold; }
    .analysis-box { background-color: #1E222D; padding: 15px; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 10px; }
    .profit-box { background-color: #161A25; padding: 15px; border-radius: 10px; border: 1px solid #00D1FF; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：雙引擎資料抓取 (Yahoo + FinMind 備援) ---
@st.cache_data(ttl=3600)
def get_stock_data_v2(symbol):
    # 預處理：如果是中文名稱，這裡可以加入對應表，目前建議輸入代碼
    ticker = f"{symbol}.TW"
    
    # Engine 1: Yahoo Finance (帶偽裝)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False, session=session)
        if df.empty:
            df = yf.download(f"{symbol}.TWO", period="1y", interval="1d", progress=False, session=session)
        
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
    except Exception as e:
        st.warning(f"Yahoo 引擎暫時受限，切換至備援引擎...")

    # Engine 2: FinMind (備援引擎)
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        parameter = {
            "dataset": "TaiwanStockPrice",
            "data_id": symbol,
            "start_date": (datetime.now() - pd.Timedelta(days=365)).strftime('%Y-%m-%d')
        }
        res = requests.get(url, params=parameter).json()
        df_fin = pd.DataFrame(res['data'])
        if not df_fin.empty:
            df_fin = df_fin.rename(columns={
                'date': 'Date', 'open': 'Open', 'high': 'High', 
                'low': 'Low', 'close': 'Close', 'Trading_Volume': 'Volume'
            })
            df_fin['Date'] = pd.to_datetime(df_fin['Date'])
            df_fin.set_index('Date', inplace=True)
            return df_fin
    except:
        pass
        
    return pd.DataFrame()

# --- 進階分析邏輯 ---
def advanced_analysis(df):
    last, prev = df.iloc[-1], df.iloc[-2]
    # K線分析
    k_msg = "盤整形態"
    if last['Close'] > last['Open'] and last['Close'] > prev['High']: k_msg = "紅K吞噬 (多頭強勢)"
    elif last['Close'] < last['Open'] and last['Close'] < prev['Low']: k_msg = "黑K吞噬 (空頭轉折)"
    
    # 123法則：1.破趨勢 2.回測 3.過高
    rule_123 = "趨勢形成中"
    if last['Close'] > df['MA20'].iloc[-1] and last['Close'] > df['High'].tail(10).max() * 0.99:
        rule_123 = "123法則：多頭確立"
        
    # 量價背離
    div_msg = "✅ 量價配合"
    if last['Close'] > prev['Close'] and last['Volume'] < df['Volume'].rolling(5).mean().iloc[-1]:
        div_msg = "⚠️ 量價背離 (價漲量縮)"
        
    return k_msg, rule_123, div_msg

# --- 側邊欄 ---
st.sidebar.header("📊 策略中心")
search_id = st.sidebar.text_input("輸入個股代號 (如: 6163 或 欣興)", value="6163")
# 獲利試算區
cost_p = st.sidebar.number_input("持股平均成本", value=0.0)
shares_n = st.sidebar.number_input("持有股數", value=0, step=1000)

# --- 主畫面 ---
df = get_stock_data_v2(search_id)
if not df.empty:
    # 指標計算
    df['MA20'] = df['Close'].rolling(20).mean()
    koudi_20 = df['Close'].iloc[-20] # 20日前扣抵價
    ma_pred = "上揚" if df['Close'].iloc[-1] > koudi_20 else "走平/下彎"
    
    # MACD
    df['EMA12'] = df['Close'].ewm(span=12).mean()
    df['EMA26'] = df['Close'].ewm(span=26).mean()
    df['DIF'] = df['EMA12'] - df['EMA26']
    df['DEA'] = df['DIF'].ewm(span=9).mean()
    df['MACD_Hist'] = df['DIF'] - df['DEA']
    
    # 預告價邏輯 (修正版)
    atr = (df['High']-df['Low']).rolling(14).mean().iloc[-1]
    vol_ratio = atr / df['Close'].iloc[-1]
    mult = 1.382 if vol_ratio < 0.03 else 0.8
    target_p = df['Close'].iloc[-1] + (df['High'].tail(20).max() - df['Low'].tail(20).min()) * mult
    days_est = max(1, round((target_p - df['Close'].iloc[-1]) / (atr * 0.85)))

    st.title(f"🚀 {search_id} 全能轉折決策看板")
    st.markdown(f"現價：<span class='up-p'>{df['Close'].iloc[-1]:.2f}</span>", unsafe_allow_html=True)

    if cost_p > 0 and shares_n > 0:
        p_profit = (target_p - cost_p) * shares_n
        p_pct = ((target_p - cost_p) / cost_p) * 100
        st.markdown(f"<div class='profit-box'><b>💎 預期獲利：</b> 達標 {target_p:.2f} 時，獲利約 <span style='color:#00D1FF'>$ {p_profit:,.0f}</span> ({p_pct:.1f}%)</div>", unsafe_allow_html=True)

    st.divider()
    
    # 分析模組
    k_m, r1, d_m = advanced_analysis(df)
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='analysis-box'><b>K線分析：</b><br>{k_m}</div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='analysis-box'><b>形態評估：</b><br>{r1}</div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='analysis-box'><b>量價關係：</b><br>{d_m}</div>", unsafe_allow_html=True)

    # 圖表
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.4, 0.15, 0.15, 0.3], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow'), name="MA20"), row=1, col=1)
    fig.add_hline(y=target_p, line_dash="dash", line_color="red", row=1, col=1)
    
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量"), row=3, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color='red', name="MACD柱"), row=4, col=1)
    
    fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    st.info(f"💡 **AI 診斷**：預計達成需 **{days_est} 個交易日**。未來均線預測為 **{ma_pred}**。MACD 目前為 **{'偏多' if df['DIF'].iloc[-1]>0 else '偏空'}**。")
else:
    st.error("❌ 雙引擎皆抓不到資料，請檢查代號或稍後再試。")
