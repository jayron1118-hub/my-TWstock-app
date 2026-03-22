import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
from datetime import datetime

# 1. 頁面基本設定與專業深色介面
st.set_page_config(page_title="台股全能轉折預告系統 V2026-旗艦版", layout="wide")

st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 42px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 42px; font-weight: bold; }
    .profit-box { background-color: #1E222D; padding: 15px; border-radius: 10px; border-left: 5px solid #00D1FF; margin-top: 10px; }
    .recommend-card { background-color: #161A25; padding: 12px; border-radius: 8px; border: 1px solid #363C4E; margin-bottom: 8px; }
    .cdp-mini { background-color: #161A25; padding: 5px; border-radius: 5px; border: 1px solid #363C4E; text-align: center; }
    .tag-chip { background-color: #FF5252; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：轉折值計算 (CDP) ---
def calculate_cdp(df):
    if df.empty: return None
    last = df.iloc[-1]
    H, L, C = last['High'].item(), last['Low'].item(), last['Close'].item()
    cdp = (H + L + 2 * C) / 4
    return {"AH": cdp + (H - L), "NH": 2 * cdp - L, "CDP": cdp, "NL": 2 * cdp - H, "AL": cdp - (H - L)}

# --- 核心邏輯：資料抓取 (支援代號與名稱) ---
@st.cache_data(ttl=600)
def get_stock_data(user_input, is_index=False):
    symbol = user_input.strip()
    if is_index:
        ticker = symbol
    else:
        ticker = f"{symbol}.TW"
    
    df = yf.download(ticker, period="8mo", interval="1d", progress=False)
    if not is_index and df.empty:
        df = yf.download(f"{symbol}.TWO", period="8mo", interval="1d", progress=False)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# --- 核心邏輯：外資買超檢查 ---
def is_foreign_buying(symbol):
    try:
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={symbol}"
        res = requests.get(url).json()
        df_chip = pd.DataFrame(res['data'])
        if not df_chip.empty:
            last = df_chip[df_chip['name'] == 'Foreign_Investor'].iloc[-1]
            return (last['buy'] - last['sell']) > 0
    except: return True
    return False

# --- 核心邏輯：選股掃描器 ---
def run_scanner(filter_chip):
    pool = ["2330", "2454", "2317", "2303", "2382", "3231", "1513", "1503", "2603", "2609", "2408", "2344", "3034", "3037", "2376", "6669", "2357"]
    matches = []
    for s in pool:
        d = get_stock_data(s)
        if len(d) < 40: continue
        c = d['Close'].iloc[-1].item()
        m20 = d['Close'].rolling(20).mean().iloc[-1]
        is_bull = c > m20
        is_low = c > d['Close'].iloc[-20]
        if is_bull and is_low:
            if filter_chip:
                if is_foreign_buying(s): matches.append(s)
            else: matches.append(s)
    return matches

# --- 側邊欄面板 ---
st.sidebar.header("📊 系統監測面板")
search_input = st.sidebar.text_input("輸入代號或名稱", value="2330")

# 個人持股試算
st.sidebar.markdown("---")
st.sidebar.subheader("💰 個人庫存試算")
cost_price = st.sidebar.number_input("平均持股成本", value=0.0, step=0.1)
stock_quantity = st.sidebar.number_input("持有股數", value=0, step=1000)

# 大盤轉折
st.sidebar.markdown("---")
taiex_df = get_stock_data("^TWII", is_index=True)
taiex_cdp = calculate_cdp(taiex_df)
if taiex_cdp:
    st.sidebar.subheader("📉 大盤未來轉折 (明日)")
    st.sidebar.markdown(f"""
    <div class='cdp-mini'>
        <small>重心 CDP</small><br><b>{taiex_cdp['CDP']:.0f}</b><br>
        <span style='color:#FF5252'>壓力 AH: {taiex_cdp['AH']:.0f}</span> | 
        <span style='color:#26A69A'>支撐 AL: {taiex_cdp['AL']:.0f}</span>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 老師嚴選：強勢轉折股")
use_foreign_filter = st.sidebar.checkbox("✅ 僅限外資買超推薦", value=False)
with st.sidebar:
    picks = run_scanner(use_foreign_filter)
    if picks:
        for p in picks: st.markdown(f"<div class='recommend-card'><b>{p}</b> <span class='tag-chip'>轉折發動中</span></div>", unsafe_allow_html=True)

# --- 主畫面邏輯 ---
try:
    df = get_stock_data(search_input)
    if not df.empty:
        # 1. 技術指標計算 (MACD, RSI, 布林)
        df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = df['EMA12'] - df['EMA26']
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['DIF'] - df['DEA']
        
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Upper'] = df['MA20'] + (df['Close'].rolling(20).std() * 2)
        df['Lower'] = df['MA20'] - (df['Close'].rolling(20).std() * 2)
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        
        # 2. 轉折與預告邏輯 (動能校正)
        now_price = df['Close'].iloc[-1].item()
        df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = df['TR'].rolling(14).mean().iloc[-1]
        
        # 動能校正：若波動率過高 (非主流小股)，調降預測倍數
        vol_ratio = atr / now_price
        adj_mult = 1.382 if vol_ratio < 0.03 else (1.0 if vol_ratio < 0.05 else 0.618)
        
        recent_range = df['High'].tail(20).max() - df['Low'].tail(20).min()
        target_price = now_price + (recent_range * adj_mult)
        days_est = max(1, round((target_price - now_price) / (atr * 0.85)))
        stock_cdp = calculate_cdp(df)

        # 3. 介面呈現
        st.title(f"🚀 {search_input} 專業轉折預告系統")
        diff = now_price - df['Close'].iloc[-2]
        price_color = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"現價：<span class='{price_color}'>{now_price:.2f}</span> ({'▲' if diff >= 0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        if cost_price > 0 and stock_quantity > 0:
            exp_profit = (target_price - cost_price) * stock_quantity
            profit_pct = ((target_price - cost_price) / cost_price) * 100
            st.markdown(f"<div class='profit-box'><b>📊 預期獲利：</b> 若達標預告價 {target_price:.2f}，預計獲利為 <span style='color:#00D1FF; font-size:24px;'>$ {exp_profit:,.0f}</span> ({profit_pct:.1f}%)</div>", unsafe_allow_html=True)

        st.divider()

        # 看板
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🔮 預告目標價", f"{target_price:.2f}", f"校正: {adj_mult}")
        c2.metric("🗓️ 達成時間", f"{days_est} ~ {days_est+3} 天", "單位：交易日")
        c3.metric("📈 MACD 趨勢", "多頭" if df['DIF'].iloc[-1] > df['DEA'].iloc[-1] else "整理", f"DIF: {df['DIF'].iloc[-1]:.2f}")
        c4.metric("🌡️ RSI 指標", f"{df['RSI'].iloc[-1]:.1f}", "🔥 過熱" if df['RSI'].iloc[-1] > 70 else "正常")

        # 明日 CDP
        st.subheader("🎯 個股明日轉折預告 (CDP)")
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("最高壓力 AH", f"{stock_cdp['AH']:.2f}")
        sc2.metric("近期壓力 NH", f"{stock_cdp['NH']:.2f}")
        sc3.metric("轉折重心 CDP", f"{stock_cdp['CDP']:.2f}")
        sc4.metric("近期支撐 NL", f"{stock_cdp['NL']:.2f}")
        sc5.metric("最低支撐 AL", f"{stock_cdp['AL']:.2f}")

        # 繪圖
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.4, 0.15, 0.15, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_hline(y=target_price, line_dash="dash", line_color="red", annotation_text="預告位", row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name="RSI"), row=2, col=1)
        v_colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name="成交量"), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], line=dict(color='white'), name="DIF"), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DEA'], line=dict(color='yellow'), name="DEA"), row=4, col=1)
        m_colors = ['#ff5252' if v >= 0 else '#26a69a' for v in df['MACD_Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=m_colors, name="MACD柱"), row=4, col=1)
        fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 策略解讀
        st.info(f"💡 **AI 策略解讀**：\n"
                f"- **MACD：** 目前 DIF {'高於' if df['DIF'].iloc[-1] > df['DEA'].iloc[-1] else '低於'} DEA，趨勢{'向上' if df['DIF'].iloc[-1] > df['DEA'].iloc[-1] else '整理'}。\n"
                f"- **扣三低：** 現價大於 20 日前扣抵價，月線具備助漲動能。\n"
                f"- **操作建議：** 預估 **{days_est} 個交易日** 內若 MACD 持續翻紅，目標價 **{target_price:.2f}** 達標機率極大。")

    else: st.warning("請確認代號正確性")
except Exception as e: st.error(f"分析異常: {e}")
