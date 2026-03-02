import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests

# 1. 頁面配置
st.set_page_config(page_title="台股全能轉折預告系統 V3", layout="wide")

# 台股紅綠燈 CSS 強化版
st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 42px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 42px; font-weight: bold; }
    .cdp-card { background-color: #161A25; padding: 15px; border-radius: 8px; border: 1px solid #363C4E; text-align: center; }
    .cdp-label { color: #888; font-size: 14px; }
    .cdp-value { color: #FFFFFF; font-size: 20px; font-weight: bold; }
    .recommend-card { background-color: #1E222D; padding: 12px; border-radius: 8px; border-left: 5px solid #FFD700; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：轉折值計算函數 ---
def calculate_cdp_levels(df):
    if df.empty: return None
    last = df.iloc[-1]
    H, L, C = last['High'].item(), last['Low'].item(), last['Close'].item()
    cdp = (H + L + 2 * C) / 4
    return {
        "AH": cdp + (H - L),
        "NH": 2 * cdp - L,
        "CDP": cdp,
        "NL": 2 * cdp - H,
        "AL": cdp - (H - L)
    }

# --- 資料抓取與修復 ---
@st.cache_data(ttl=600)
def get_data(symbol, period="8mo"):
    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return pd.DataFrame()

# --- 側邊欄控制 ---
st.sidebar.header("📊 系統監測面板")
target_stock = st.sidebar.text_input("輸入個股代號 (如: 2330)", value="2330")
use_foreign_filter = st.sidebar.checkbox("✅ 僅限外資買超推薦", value=False)

# --- A. 台指未來轉折值區塊 (大盤環境) ---
st.sidebar.markdown("---")
st.sidebar.subheader("📉 大盤未來轉折 (台指/加權)")
twii_df = get_data("^TWII", period="5d")
twii_cdp = calculate_cdp_levels(twii_df)

if twii_cdp:
    with st.sidebar:
        cols = st.columns(2)
        cols[0].markdown(f"<div class='cdp-card'><span class='cdp-label'>最高壓力 AH</span><br><span class='cdp-value' style='color:#FF5252'>{twii_cdp['AH']:.0f}</span></div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div class='cdp-card'><span class='cdp-label'>近期壓力 NH</span><br><span class='cdp-value' style='color:#FFB74D'>{twii_cdp['NH']:.0f}</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='cdp-card' style='margin: 5px 0;'><span class='cdp-label'>轉折重心 CDP</span><br><span class='cdp-value'>{twii_cdp['CDP']:.0f}</span></div>", unsafe_allow_html=True)
        cols = st.columns(2)
        cols[0].markdown(f"<div class='cdp-card'><span class='cdp-label'>近期支撐 NL</span><br><span class='cdp-value' style='color:#4DB6AC'>{twii_cdp['NL']:.0f}</span></div>", unsafe_allow_html=True)
        cols[1].markdown(f"<div class='cdp-card'><span class='cdp-label'>最低支撐 AL</span><br><span class='cdp-value' style='color:#26A69A'>{twii_cdp['AL']:.0f}</span></div>", unsafe_allow_html=True)

# --- B. 個股選股與主畫面 ---
try:
    # 處理代號後綴
    full_symbol = f"{target_stock}.TW"
    df = get_data(full_symbol)
    if df.empty:
        full_symbol = f"{target_stock}.TWO"
        df = get_data(full_symbol)

    if not df.empty:
        # 計算技術指標
        df['MA20'] = df['Close'].rolling(20).mean()
        df['STD'] = df['Close'].rolling(20).std()
        df['Upper'] = df['MA20'] + (df['STD'] * 2)
        df['Lower'] = df['MA20'] - (df['STD'] * 2)
        
        # 計算個股未來轉折
        stock_cdp = calculate_cdp_levels(df)
        
        now_price = df['Close'].iloc[-1].item()
        prev_price = df['Close'].iloc[-2].item()
        diff = now_price - prev_price
        
        # 標題與現價
        st.title(f"🚀 {target_stock} 轉折預告與策略系統")
        price_color = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"現價：<span class='{price_color}'>{now_price:.2f}</span> "
                    f"({'▲' if diff >= 0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        # --- 新增：個股明日轉折值看板 ---
        st.subheader("🎯 個股未來(明日)轉折預告值")
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("最高壓力(AH)", f"{stock_cdp['AH']:.2f}")
        sc2.metric("近期壓力(NH)", f"{stock_cdp['NH']:.2f}")
        sc3.metric("轉折重心(CDP)", f"{stock_cdp['CDP']:.2f}")
        sc4.metric("近期支撐(NL)", f"{stock_cdp['NL']:.2f}")
        sc5.metric("最低支撐(AL)", f"{stock_cdp['AL']:.2f}")
        st.caption("※ 基於今日 K 線數據計算明日操作區間")

        st.divider()

        # 策略資訊區
        c1, c2 = st.columns(2)
        with c1:
            st.success("🎯 建議入場區間")
            st.subheader(f"{df['Lower'].iloc[-1]:.2f} ~ {df['MA20'].iloc[-1]:.2f}")
        with c2:
            st.info("🔮 趨勢扣抵狀況")
            deduct_price = df['Close'].iloc[-20]
            st.subheader(f"現價 {'高於' if now_price > deduct_price else '低於'} 扣抵位")
            st.write(f"20日前扣抵價：{deduct_price:.2f}")

        # 繪圖 (K線 + 布林)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='rgba(255,255,255,0.2)'), name="天線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='rgba(255,255,255,0.2)'), name="地線"), row=1, col=1)
        
        # 成交量
        v_colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name="成交量"), row=2, col=1)
        
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 深度策略
        st.markdown(f"""
        <div style="background-color:#1E222D; padding:20px; border-radius:10px; border-left: 5px solid #FFD700;">
        <h3>💡 江江風格 - 核心決策</h3>
        <ul>
            <li><b>轉折操作：</b>明日若開在 <b>{stock_cdp['NH']:.2f} (NH)</b> 之上，代表多頭極強，可順勢看 <b>{stock_cdp['AH']:.2f}</b>。</li>
            <li><b>支撐關鍵：</b>若股價跌破 <b>{stock_cdp['NL']:.2f} (NL)</b>，代表進入弱勢整理，建議在 <b>{stock_cdp['AL']:.2f}</b> 附近分批低接。</li>
            <li><b>趨勢：</b>目前月線呈{'上揚' if now_price > deduct_price else '扣抵壓力'}，{'多頭格局未變' if now_price > df['MA20'].iloc[-1] else '回測月線尋找支撐'}。</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("請確認代號正確性 (如: 2330)")
except Exception as e:
    st.error(f"分析異常: {e}")
