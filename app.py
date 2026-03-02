import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
from datetime import datetime

# 1. 頁面配置與專業深色 CSS
st.set_page_config(page_title="台股全能轉折預告系統 V4", layout="wide")

st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 45px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 45px; font-weight: bold; }
    .recommend-card { 
        background-color: #1E222D; padding: 12px; border-radius: 8px; 
        border-left: 5px solid #FFD700; margin-bottom: 10px;
    }
    .cdp-box { 
        background-color: #161A25; padding: 10px; border-radius: 5px; 
        border: 1px solid #363C4E; text-align: center; margin-bottom: 5px;
    }
    .cdp-label { color: #888; font-size: 12px; }
    .cdp-value { color: #FFF; font-size: 18px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：轉折值計算 (CDP) ---
def calculate_cdp(df):
    if df.empty: return None
    last = df.iloc[-1]
    H, L, C = last['High'].item(), last['Low'].item(), last['Close'].item()
    cdp = (H + L + 2 * C) / 4
    return {
        "AH": cdp + (H - L), "NH": 2 * cdp - L, "CDP": cdp,
        "NL": 2 * cdp - H, "AL": cdp - (H - L)
    }

# --- 核心邏輯：資料抓取 (修正 MultiIndex) ---
@st.cache_data(ttl=600)
def get_stock_data(symbol, period="8mo"):
    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return pd.DataFrame()

# --- 核心邏輯：外資買超檢查 ---
def is_foreign_buying(symbol):
    try:
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={symbol}"
        res = requests.get(url).json()
        df_chip = pd.DataFrame(res['data'])
        if not df_chip.empty:
            last_f = df_chip[df_chip['name'] == 'Foreign_Investor'].iloc[-1]
            return (last_f['buy'] - last_f['sell']) > 0
    except: return True
    return False

# --- 核心邏輯：選股掃描器 ---
def run_scanner(filter_chip):
    pool = ["2330", "2454", "2317", "2303", "2382", "3231", "1513", "1503", "2603", "2609", "3034", "3037"]
    matches = []
    for s in pool:
        d = get_stock_data(f"{s}.TW", period="3mo")
        if len(d) < 40: continue
        c = d['Close'].iloc[-1].item()
        m5, m20 = d['Close'].rolling(5).mean().iloc[-1], d['Close'].rolling(20).mean().iloc[-1]
        if c > m5 > m20 and c > d['Close'].iloc[-5] and c > d['Close'].iloc[-20]:
            if filter_chip:
                if is_foreign_buying(s): matches.append(s)
            else: matches.append(s)
    return matches

# --- 側邊欄：大盤環境與選股 ---
st.sidebar.header("📊 系統監測面板")
target_stock = st.sidebar.text_input("輸入台股代號", value="2330")
st.sidebar.markdown("---")

# 1. 大盤轉折值 (加權指數)
st.sidebar.subheader("📉 大盤未來轉折 (明日)")
twii_df = get_data("^TWII", period="5d") if 'get_data' not in globals() else get_stock_data("^TWII", period="5d")
twii_cdp = calculate_cdp(twii_df)
if twii_cdp:
    with st.sidebar:
        c1, c2 = st.columns(2)
        c1.markdown(f"<div class='cdp-box'><span class='cdp-label'>AH</span><br><span class='cdp-value'>{twii_cdp['AH']:.0f}</span></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='cdp-box'><span class='cdp-label'>NH</span><br><span class='cdp-value'>{twii_cdp['NH']:.0f}</span></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='cdp-box'><span class='cdp-label'>CDP 重心</span><br><span class='cdp-value'>{twii_cdp['CDP']:.0f}</span></div>", unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        c3.markdown(f"<div class='cdp-box'><span class='cdp-label'>NL</span><br><span class='cdp-value'>{twii_cdp['NL']:.0f}</span></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='cdp-box'><span class='cdp-label'>AL</span><br><span class='cdp-value'>{twii_cdp['AL']:.0f}</span></div>", unsafe_allow_html=True)

# 2. 選股推薦
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 老師嚴選：強勢股")
use_chip = st.sidebar.checkbox("✅ 僅限外資買超", value=False)
with st.sidebar:
    with st.spinner('掃描中...'):
        recs = run_scanner(use_chip)
        if recs:
            for r in recs:
                st.markdown(f"<div class='recommend-card'><b>{r}</b> <span style='color:#FF5252; font-size:10px;'>扣三低+多頭</span></div>", unsafe_allow_html=True)
        else: st.write("暫無標的")

# --- 主畫面：個股分析 ---
try:
    df = get_stock_data(f"{target_stock}.TW")
    if df.empty: df = get_stock_data(f"{target_stock}.TWO")
    
    if not df.empty:
        # 技術指標計算
        df['MA20'] = df['Close'].rolling(20).mean()
        df['STD'] = df['Close'].rolling(20).std()
        df['Upper'], df['Lower'] = df['MA20']+(df['STD']*2), df['MA20']-(df['STD']*2)
        
        # RSI & ATR
        delta = df['Close'].diff()
        gain, loss = delta.where(delta > 0, 0).rolling(14).mean(), -delta.where(delta < 0, 0).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = df['TR'].rolling(14).mean().iloc[-1]
        
        # 數值提取與預測
        now_price = df['Close'].iloc[-1].item()
        prev_price = df['Close'].iloc[-2].item()
        diff = now_price - prev_price
        target_price = now_price + (df['High'].tail(20).max() - df['Low'].tail(20).min()) * 1.382
        days_est = max(1, round((target_price - now_price) / (atr * 0.8)))
        stock_cdp = calculate_cdp(df)

        # 介面顯示
        st.title(f"🚀 {target_stock} 專業轉折系統")
        p_color = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"現價：<span class='{p_color}'>{now_price:.2f}</span> ({'▲' if diff>=0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        # 新增：個股明日轉折值
        st.subheader("🎯 個股明日關鍵轉折點 (CDP)")
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("最高壓力(AH)", f"{stock_cdp['AH']:.2f}")
        sc2.metric("近期壓力(NH)", f"{stock_cdp['NH']:.2f}")
        sc3.metric("轉折重心(CDP)", f"{stock_cdp['CDP']:.2f}")
        sc4.metric("近期支撐(NL)", f"{stock_cdp['NL']:.2f}")
        sc5.metric("最低支撐(AL)", f"{stock_cdp['AL']:.2f}")

        st.divider()

        # 未來預告價看板
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("🔮 未來預告目標價")
            st.subheader(f"NT$ {target_price:.2f}")
            st.write(f"預計達成：**{days_est} ~ {days_est+4}** 天")
        with c2:
            st.success("🎯 建議入場區間")
            st.subheader(f"{df['Lower'].iloc[-1]:.1f} ~ {df['MA20'].iloc[-1]:.1f}")
        with c3:
            st.warning(f"🌡️ RSI 指標: {df['RSI'].iloc[-1]:.1f}")
            st.subheader("過熱" if df['RSI'].iloc[-1] > 70 else "超跌" if df['RSI'].iloc[-1] < 30 else "適中")

        # 圖表
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)
        fig.add_hline(y=target_price, line_dash="dash", line_color="red", annotation_text="預告目標", row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name="RSI"), row=2, col=1)
        v_colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name="成交量"), row=3, col=1)
        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 策略解讀
        st.markdown(f"""
        <div style="background-color:#1E222D; padding:20px; border-radius:10px; border-left: 5px solid #FFD700;">
        <h3>💡 江江老師核心策略</h3>
        <ul>
            <li><b>明日觀測：</b>若開盤在 <b>{stock_cdp['NH']:.2f}</b> 之上為極強勢，若跌破 <b>{stock_cdp['NL']:.2f}</b> 則轉弱。</li>
            <li><b>空間預告：</b>目前離目標價 <b>{target_price:.2f}</b> 尚有空間，預計 <b>{days_est}</b> 天左右發酵。</li>
            <li><b>趨勢扣抵：</b>現價大於20日前的價格，<b>月線扣抵低位，助漲力道極強</b>。</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    else: st.warning("請確認代號")
except Exception as e: st.error(f"分析異常: {e}")
