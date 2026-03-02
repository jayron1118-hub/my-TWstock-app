import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
from datetime import datetime, timedelta

# 1. 頁面基本設定與專業深色 CSS
st.set_page_config(page_title="台股全能轉折預告系統 V2026", layout="wide")

st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 48px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 48px; font-weight: bold; }
    .recommend-card { 
        background-color: #1E222D; 
        padding: 15px; 
        border-radius: 10px; 
        border-left: 5px solid #FFD700; 
        margin-bottom: 15px;
    }
    .cdp-box {
        background-color: #161A25;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
        border: 1px solid #363C4E;
    }
    .tag-chip { 
        background-color: #FF5252; 
        color: white; 
        padding: 2px 6px; 
        border-radius: 4px; 
        font-size: 11px; 
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：轉折值計算 (CDP) ---
def calculate_cdp(df):
    if df.empty: return None
    last = df.iloc[-1]
    H, L, C = last['High'], last['Low'], last['Close']
    cdp = (H + L + 2 * C) / 4
    return {
        "AH": cdp + (H - L),
        "NH": 2 * cdp - L,
        "CDP": cdp,
        "NL": 2 * cdp - H,
        "AL": cdp - (H - L)
    }

# --- 核心邏輯：資料抓取 ---
@st.cache_data(ttl=600)
def get_stock_data(symbol, is_index=False):
    try:
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
    except:
        return pd.DataFrame()

# --- 核心邏輯：外資買超檢查 ---
def is_foreign_buying(symbol):
    try:
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={symbol}"
        res = requests.get(url).json()
        df_chip = pd.DataFrame(res['data'])
        if not df_chip.empty:
            last_foreign = df_chip[df_chip['name'] == 'Foreign_Investor'].iloc[-1]
            return (last_foreign['buy'] - last_foreign['sell']) > 0
    except:
        return True
    return False

# --- 核心邏輯：全自動選股掃描器 ---
def run_scanner(filter_chip):
    pool = ["2330", "2454", "2317", "2303", "2382", "3231", "1513", "1503", "2603", "2609", "2408", "2344", "3034", "3037", "2376", "6669", "2357"]
    matches = []
    for s in pool:
        d = get_stock_data(s)
        if len(d) < 40: continue
        c = d['Close'].iloc[-1].item()
        m5 = d['Close'].rolling(5).mean().iloc[-1]
        m20 = d['Close'].rolling(20).mean().iloc[-1]
        is_bull = c > m5 > m20
        is_low = c > d['Close'].iloc[-5] and c > d['Close'].iloc[-10] and c > d['Close'].iloc[-20]
        if is_bull and is_low:
            if filter_chip:
                if is_foreign_buying(s): matches.append(s)
            else: matches.append(s)
    return matches

# --- 側邊欄：台指大盤轉折與選股 ---
st.sidebar.header("📊 系統監測面板")
target_stock = st.sidebar.text_input("輸入個股代號", value="2330")

# 新增：台指未來轉折值顯示
st.sidebar.markdown("---")
st.sidebar.subheader("📉 台指大盤未來轉折")
taiex_df = get_stock_data("^TWII", is_index=True)
taiex_cdp = calculate_cdp(taiex_df)
if taiex_cdp:
    with st.sidebar:
        st.markdown(f"""
        <div class='cdp-box'>
            <small>重心 CDP</small><br><b>{taiex_cdp['CDP']:.0f}</b><br>
            <small style='color:#FF5252'>壓力 AH: {taiex_cdp['AH']:.0f}</small> | 
            <small style='color:#26A69A'>支撐 AL: {taiex_cdp['AL']:.0f}</small>
        </div>
        """, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 老師嚴選：強勢轉折股")
use_foreign_filter = st.sidebar.checkbox("✅ 僅限外資買超推薦", value=False)

with st.sidebar:
    with st.spinner('掃描標的中...'):
        recommended_stocks = run_scanner(use_foreign_filter)
        if recommended_stocks:
            for rs in recommended_stocks:
                st.markdown(f"<div class='recommend-card'><b>{rs}</b> <span class='tag-chip'>扣三低+多頭</span></div>", unsafe_allow_html=True)
        else:
            st.write("目前暫無符合標的")

# --- 主畫面：儀表板邏輯 ---
try:
    df = get_stock_data(target_stock)
    if not df.empty:
        # 技術指標計算
        df['MA20'] = df['Close'].rolling(20).mean()
        df['STD'] = df['Close'].rolling(20).std()
        df['Upper'] = df['MA20'] + (df['STD'] * 2)
        df['Lower'] = df['MA20'] - (df['STD'] * 2)
        
        # RSI & ATR
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = df['TR'].rolling(14).mean().iloc[-1]
        
        # 轉折值計算 (CDP)
        stock_cdp = calculate_cdp(df)
        
        # 數據提取
        now_price = df['Close'].iloc[-1].item()
        prev_price = df['Close'].iloc[-2].item()
        diff = now_price - prev_price
        rsi_val = df['RSI'].iloc[-1].item()
        
        # 未來預告價 (1.382 對稱增長)
        recent_range = df['High'].tail(20).max() - df['Low'].tail(20).min()
        target_price = now_price + (recent_range * 1.382)
        days_est = max(1, round((target_price - now_price) / (atr * 0.8)))

        # --- 顯示介面 ---
        st.title(f"🚀 {target_stock} 專業轉折預告系統")
        price_color = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"現價：<span class='{price_color}'>{now_price:.2f}</span> ({'▲' if diff >= 0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        st.divider()

        # 第一排：預告價與天數
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.metric("🔮 未來預告目標價", f"{target_price:.2f}", f"預計 {days_est} ~ {days_est+4} 天")
        with col_t2:
            st.metric("🌡️ RSI 過熱指標", f"{rsi_val:.1f}", "🔥 過熱" if rsi_val > 70 else "正常")
        with col_t3:
            st.metric("🏠 扣抵位關係", f"{df['Close'].iloc[-20]:.2f}", "助漲中" if now_price > df['Close'].iloc[-20] else "壓力中")

        # 第二排：個股未來(明日)轉折值 (CDP)
        st.subheader("🎯 個股未來(明日)轉折值 (CDP系統)")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("最高壓力 AH", f"{stock_cdp['AH']:.2f}")
        c2.metric("近期壓力 NH", f"{stock_cdp['NH']:.2f}")
        c3.metric("轉折重心 CDP", f"{stock_cdp['CDP']:.2f}")
        c4.metric("近期支撐 NL", f"{stock_cdp['NL']:.2f}")
        c5.metric("最低支撐 AL", f"{stock_cdp['AL']:.2f}")

        # 繪圖
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='gray', width=1, dash='dot'), name="天線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='gray', width=1, dash='dot'), name="地線"), row=1, col=1)
        
        # 標註未來預告價線
        fig.add_hline(y=target_price, line_dash="dash", line_color="red", annotation_text="預告噴發位", row=1, col=1)

        # RSI & 成交量
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name="RSI"), row=2, col=1)
        v_colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name="成交量"), row=3, col=1)

        fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 策略解讀
        st.markdown(f"""
        <div style="background-color:#1E222D; padding:20px; border-radius:10px; border-left: 5px solid #FFD700;">
        <h3>💡 江江風格 - 深度策略解讀</h3>
        <ul>
            <li><b>未來轉折：</b>明日若開在 <b>{stock_cdp['NH']:.2f}</b> 之上代表極強勢，目標直指 <b>{target_price:.2f}</b>。</li>
            <li><b>進場區間：</b>最佳防守位在月線至支撐線 <b>{df['Lower'].iloc[-1]:.2f}</b> 之間，不破即是買點。</li>
            <li><b>時間預告：</b>依波動率推算，此波轉折預計在 <b>{days_est+2}</b> 個交易日內見分曉。</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.warning("請確認代號正確性")
except Exception as e:
    st.error(f"系統分析異常: {e}")

st.sidebar.caption(f"最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
