import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
from datetime import datetime

import time
import requests

# 解決 Streamlit Cloud 暫存權限問題
try:
    import appdirs as ad
    ad.user_cache_dir = lambda *args: "/tmp"
except:
    pass

@st.cache_data(ttl=3600)  # 將快取時間延長至 1 小時，減少請求次數
def get_stock_data(symbol, is_index=False):
    ticker_str = symbol if is_index else f"{symbol}.TW"
    
    # 建立偽裝 Session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    for attempt in range(3):  # 最多嘗試 3 次
        try:
            df = yf.download(ticker_str, period="1y", interval="1d", progress=False, session=session)
            
            if not is_index and df.empty:
                df = yf.download(f"{symbol}.TWO", period="1y", interval="1d", progress=False, session=session)
            
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
                
        except Exception as e:
            if "429" in str(e) or "Rate limited" in str(e):
                time.sleep(2 * (attempt + 1))  # 遇到限流，睡一下再試
            continue
            
    return pd.DataFrame()

# 1. 頁面配置與專業深色介面
st.set_page_config(page_title="台股全能轉折預告系統 - 旗艦進化版", layout="wide")

st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 42px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 42px; font-weight: bold; }
    .profit-box { background-color: #1E222D; padding: 15px; border-radius: 10px; border-left: 5px solid #00D1FF; margin-top: 10px; }
    .analysis-box { background-color: #161A25; padding: 12px; border-radius: 8px; border: 1px solid #363C4E; margin-bottom: 8px; }
    .tag-chip { background-color: #FF5252; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：資料抓取與名稱轉換 ---
@st.cache_data(ttl=600)
def get_stock_data(user_input, is_index=False):
    symbol = user_input.strip()
    # 支援繁體中文搜尋 (透過 yfinance 內建模糊比對，但代號仍為優先)
    ticker = symbol if is_index else (f"{symbol}.TW" if symbol.isdigit() else symbol)
    
    df = yf.download(ticker, period="1y", interval="1d", progress=False)
    if not is_index and df.empty and symbol.isdigit():
        df = yf.download(f"{symbol}.TWO", period="1y", interval="1d", progress=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# --- 進階技術分析函數 ---
def analyze_trends(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    # 1. K線形態簡單辨識
    k_pattern = "盤整"
    body = last['Close'] - last['Open']
    if last['Close'] > last['Open'] and last['Low'] < prev['Low'] and last['Close'] > prev['High']:
        k_pattern = "多頭吞噬 (強勢)"
    elif last['Close'] < last['Open'] and last['High'] > prev['High'] and last['Close'] < prev['Low']:
        k_pattern = "空頭吞噬 (弱勢)"
    
    # 2. 123法則模擬 (1. 破趨勢 2. 測試不破 3. 突破前高)
    rule_123 = "趨勢形成中"
    if last['Close'] > df['MA20'].iloc[-1] and df['DIF'].iloc[-1] > df['DEA'].iloc[-1]:
        rule_123 = "123法則：多頭確立"
    
    # 3. 量價背離
    divergence = "量價配合"
    if last['Close'] > prev['Close'] and last['Volume'] < df['Volume'].rolling(5).mean().iloc[-1]:
        divergence = "警告：量價背離 (價漲量縮)"
    
    return k_pattern, rule_123, divergence

# --- 側邊欄 ---
st.sidebar.header("📊 系統監測面板")
search_input = st.sidebar.text_input("輸入代號或中文名稱", value="2330")

# 庫存試算區
st.sidebar.markdown("---")
st.sidebar.subheader("💰 個人庫存試算")
avg_cost = st.sidebar.number_input("平均持股成本", value=0.0, step=0.1)
shares = st.sidebar.number_input("持有股數 (張=1000)", value=0, step=1000)

# --- 主畫面邏輯 ---
try:
    df = get_stock_data(search_input)
    if not df.empty:
        # 技術指標計算
        df['MA20'] = df['Close'].rolling(20).mean()
        # 未來均線扣抵預測
        koudi_20 = df['Close'].iloc[-20]
        # MACD
        df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = df['EMA12'] - df['EMA26']
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['DIF'] - df['DEA']
        
        # 動能校正預告價 (修正過於樂觀問題)
        now_price = df['Close'].iloc[-1].item()
        df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = df['TR'].rolling(14).mean().iloc[-1]
        
        # 修正係數：若波動率過高 (非主流股)，調降預測倍數
        vol_ratio = atr / now_price
        adj_mult = 1.382 if vol_ratio < 0.03 else (1.0 if vol_ratio < 0.05 else 0.618)
        
        recent_range = df['High'].tail(20).max() - df['Low'].tail(20).min()
        target_price = now_price + (recent_range * adj_mult)
        days_est = max(1, round((target_price - now_price) / (atr * 0.85)))

        # 介面呈現
        st.title(f"🚀 {search_input} 專業策略儀表板")
        diff = now_price - df['Close'].iloc[-2]
        p_color = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"現價：<span class='{p_color}'>{now_price:.2f}</span> ({'▲' if diff >= 0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        if avg_cost > 0 and shares > 0:
            potential_profit = (target_price - avg_cost) * shares
            profit_pct = ((target_price - avg_cost) / avg_cost) * 100
            st.markdown(f"<div class='profit-box'><b>📊 獲利預期：</b> 若達標預告價 {target_price:.2f}，預計獲利為 <span style='color:#00D1FF; font-size:24px;'>$ {potential_profit:,.0f}</span> ({profit_pct:.1f}%)</div>", unsafe_allow_html=True)

        st.divider()

        # 進階分析看板
        k_pat, r123, div_msg = analyze_trends(df)
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div class='analysis-box'><b>K線形態：</b><br>{k_pat}</div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='analysis-box'><b>趨勢評估：</b><br>{r123}</div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='analysis-box'><b>量價關係：</b><br>{div_msg}</div>", unsafe_allow_html=True)

        # 數據看板
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🔮 預告目標價", f"{target_price:.2f}", f"校正: {adj_mult}")
        m2.metric("🗓️ 達成時間", f"{days_est} ~ {days_est+3} 天", "單位：交易日")
        m3.metric("🌙 月線扣抵預測", f"{koudi_20:.2f}", "助漲" if now_price > koudi_20 else "阻力")
        m4.metric("📈 MACD 狀態", "金叉" if df['DIF'].iloc[-1] > df['DEA'].iloc[-1] else "死叉", f"DIF: {df['DIF'].iloc[-1]:.2f}")

        # 繪圖 (四層架構)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.4, 0.15, 0.15, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_hline(y=target_price, line_dash="dash", line_color="red", annotation_text="預告位", row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)
        
        # RSI/Volume/MACD
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], line=dict(color='white'), name="DIF"), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], line=dict(color='yellow'), name="DEA"), row=4, col=1)
        m_colors = ['#ff5252' if v >= 0 else '#26a69a' for v in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=m_colors, name="MACD柱"), row=4, col=1)

        fig.update_layout(height=1100, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 深度解讀
        st.info(f"💡 **AI 決策建議**：\n"
                f"- **時間說明：** 預計達成時間為 **{days_est} 個交易日** (不含假日)。\n"
                f"- **均線預測：** 目前現價 {'高於' if now_price > koudi_20 else '低於'} 20日前扣抵價 {koudi_20:.2f}，月線預計持續{'上揚助漲' if now_price > koudi_20 else '走平或下彎'}。\n"
                f"- **MACD深度：** DIF 位於零軸{'上' if df['DIF'].iloc[-1] > 0 else '下'}，代表{'中長線多頭格局' if df['DIF'].iloc[-1] > 0 else '中長線空頭格局'}。")
    else: st.warning("請確認代號或名稱正確性")
except Exception as e: st.error(f"分析異常: {e}")
