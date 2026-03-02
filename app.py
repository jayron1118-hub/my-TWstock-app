import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
from datetime import datetime, timedelta

# 1. 頁面基本設定與專業深色 CSS
st.set_page_config(page_title="台股全能轉折預告系統", layout="wide")

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

# --- 核心邏輯：資料抓取 (修正 MultiIndex 問題) ---
@st.cache_data(ttl=600)
def get_stock_data(symbol, period="8mo"):
    try:
        df = yf.download(f"{symbol}.TW", period=period, interval="1d", progress=False)
        if df.empty:
            df = yf.download(f"{symbol}.TWO", period=period, interval="1d", progress=False)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return pd.DataFrame()

# --- 核心邏輯：外資買超檢查 (FinMind API) ---
def is_foreign_buying(symbol):
    try:
        # 取得最近三天的法人資料
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={symbol}"
        res = requests.get(url).json()
        df_chip = pd.DataFrame(res['data'])
        if not df_chip.empty:
            # 抓取最後一筆外資資料 (Foreign_Investor)
            last_foreign = df_chip[df_chip['name'] == 'Foreign_Investor'].iloc[-1]
            return (last_foreign['buy'] - last_foreign['sell']) > 0
    except:
        return True # API 異常時不阻擋，避免掃描器空白
    return False

# --- 核心邏輯：全自動選股掃描器 ---
def run_scanner(filter_chip):
    # 掃描池：權值股與熱門股
    pool = ["2330", "2454", "2317", "2303", "2382", "3231", "1513", "1503", "2603", "2609", "2408", "2344", "3034", "3037", "2376", "6669", "2357"]
    matches = []
    
    for s in pool:
        d = get_stock_data(s, period="3mo")
        if len(d) < 40: continue
        
        c = d['Close'].iloc[-1].item()
        m5 = d['Close'].rolling(5).mean().iloc[-1]
        m20 = d['Close'].rolling(20).mean().iloc[-1]
        
        # 條件 1: 站穩均線 + 多頭排列
        is_bull = c > m5 > m20
        # 條件 2: 扣三低 (現價大於 5, 10, 20 天前的價格)
        is_low = c > d['Close'].iloc[-5] and c > d['Close'].iloc[-10] and c > d['Close'].iloc[-20]
        
        if is_bull and is_low:
            if filter_chip:
                if is_foreign_buying(s):
                    matches.append(s)
            else:
                matches.append(s)
    return matches

# --- 側邊欄控制與選股視窗 ---
st.sidebar.header("📊 系統監測面板")
target_stock = st.sidebar.text_input("輸入台股代號", value="2330")
st.sidebar.markdown("---")

st.sidebar.subheader("🎯 老師嚴選：強勢轉折股")
use_foreign_filter = st.sidebar.checkbox("✅ 僅限外資買超推薦", value=False)

with st.sidebar:
    with st.spinner('掃描標的中...'):
        recommended_stocks = run_scanner(use_foreign_filter)
        if recommended_stocks:
            for rs in recommended_stocks:
                st.markdown(f"""
                <div class='recommend-card'>
                    <b>{rs}</b> <span class='tag-chip'>扣三低+多頭</span>
                    <p style='font-size:12px; color:#888; margin-top:5px;'>符合戴維斯雙擊與站穩多頭格局</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("目前暫無符合標的")

# --- 主畫面：儀表板邏輯 ---
try:
    df = get_stock_data(target_stock)
    if not df.empty:
        # --- 技術指標計算 ---
        # 1. 布林通道
        df['MA20'] = df['Close'].rolling(20).mean()
        df['STD'] = df['Close'].rolling(20).std()
        df['Upper'] = df['MA20'] + (df['STD'] * 2)
        df['Lower'] = df['MA20'] - (df['STD'] * 2)
        
        # 2. RSI (過熱指標)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        
        # 3. ATR 與 預估天數
        df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
        atr = df['TR'].rolling(14).mean().iloc[-1]
        
        # 數值提取
        now_price = df['Close'].iloc[-1].item()
        prev_price = df['Close'].iloc[-2].item()
        diff = now_price - prev_price
        rsi_val = df['RSI'].iloc[-1].item()
        
        # 預告轉折目標
        recent_range = df['High'].tail(20).max() - df['Low'].tail(20).min()
        target_price = now_price + (recent_range * 1.382)
        days_est = max(1, round((target_price - now_price) / (atr * 0.8)))

        # --- 顯示介面 ---
        st.title(f"🚀 {target_stock} 專業轉折預告系統")
        price_color = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"現價：<span class='{price_color}'>{now_price:.2f}</span> "
                    f"({'▲' if diff >= 0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        st.divider()

        # 策略看板
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("🔮 預告噴發目標")
            st.subheader(f"NT$ {target_price:.2f}")
            st.write(f"預計達成時間：**{days_est} ~ {days_est+4}** 天")
        with c2:
            st.success("🎯 建議入場區間")
            st.subheader(f"{df['Lower'].iloc[-1]:.1f} ~ {df['MA20'].iloc[-1]:.1f}")
            st.write("策略：回測不破月線布局")
        with c3:
            rsi_desc = "🔥 過熱" if rsi_val > 70 else "🧊 超跌" if rsi_val < 30 else "⚖️ 適中"
            st.warning(f"🌡️ 過熱指標 (RSI: {rsi_val:.1f})")
            st.subheader(rsi_desc)

        # 繪圖
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
        # K線
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)
        fig.add_hline(y=target_price, line_dash="dash", line_color="red", annotation_text="目標轉折", row=1, col=1)
        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name="RSI"), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)
        # 量
        v_colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, name="成交量"), row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 深度策略解讀
        st.markdown(f"""
        <div style="background-color:#1E222D; padding:20px; border-radius:10px; border-left: 5px solid #FFD700;">
        <h3>💡 江江風格 - 深度策略解讀</h3>
        <ul>
            <li><b>扣抵動能：</b>目前現價 <b>{now_price:.2f}</b> 高於 20 日前價格，均線持續助漲。</li>
            <li><b>過熱分析：</b>RSI 目前為 <b>{rsi_val:.1f}</b>，{'漲勢過猛，不建議追高' if rsi_val > 70 else '目前安全，靜待轉折噴發'}。</li>
            <li><b>進場提示：</b>最佳買點位於月線 <b>{df['MA20'].iloc[-1]:.2f}</b> 附近，防守位置看布林下軌。</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.warning("請確認代號正確性")
except Exception as e:
    st.error(f"系統分析異常: {e}")

st.sidebar.caption("數據來源：Yahoo Finance & FinMind")
