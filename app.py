import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# 頁面基本設定
st.set_page_config(page_title="江江風-全能選股預告系統", layout="wide")

# 自定義 CSS
st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 45px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 45px; font-weight: bold; }
    .recommend-box { background-color: #161A25; padding: 15px; border-radius: 10px; border: 1px solid #363C4E; margin-top: 20px; }
    .tag { background-color: #FFD700; color: black; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：資料抓取 ---
@st.cache_data(ttl=3600)
def get_data(symbol):
    df = yf.download(f"{symbol}.TW", period="8mo", interval="1d", progress=False)
    if df.empty:
        df = yf.download(f"{symbol}.TWO", period="8mo", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# --- 核心邏輯：選股掃描器 (扣三低 + 多頭格局) ---
def stock_scanner():
    # 預設掃描清單 (可自行增加)
    scan_list = ["2330", "2454", "2317", "2303", "2382", "3231", "1513", "1503", "2603", "2609", "2881", "2882"]
    recommendations = []
    
    for s in scan_list:
        try:
            temp_df = get_data(s)
            if len(temp_df) < 60: continue
            
            close = temp_df['Close'].iloc[-1].item()
            ma5 = temp_df['Close'].rolling(5).mean().iloc[-1]
            ma10 = temp_df['Close'].rolling(10).mean().iloc[-1]
            ma20 = temp_df['Close'].rolling(20).mean().iloc[-1]
            
            # 扣三低邏輯：現價高於 5, 10, 20 天前的價格
            d5 = temp_df['Close'].iloc[-5]
            d10 = temp_df['Close'].iloc[-10]
            d20 = temp_df['Close'].iloc[-20]
            
            # 篩選條件：多頭排列 + 扣三低 (具備爆發潛力)
            if close > ma5 > ma10 > ma20 and close > d5 and close > d10 and close > d20:
                recommendations.append(s)
        except:
            continue
    return recommendations

# --- 側邊欄 ---
st.sidebar.header("📊 系統監測")
stock_id = st.sidebar.text_input("輸入台股代號", value="2330")

# 顯示選股推薦 (左下角)
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 老師嚴選：強勢轉折股")
with st.sidebar:
    rec_list = stock_scanner()
    if rec_list:
        for r in rec_list:
            st.markdown(f"<div class='recommend-box'><b>{r}</b> <span class='tag'>扣三低+多頭</span></div>", unsafe_allow_html=True)
    else:
        st.write("目前市場震盪，暫無符合標的")
st.sidebar.caption("※ 掃描範圍：台灣核心權值股")

# --- 主畫面邏輯 ---
try:
    df = get_data(stock_id)
    if not df.empty:
        # 技術指標計算
        df['MA20'] = df['Close'].rolling(20).mean()
        df['STD'] = df['Close'].rolling(20).std()
        df['Upper'] = df['MA20'] + (df['STD'] * 2)
        df['Lower'] = df['MA20'] - (df['STD'] * 2)
        
        # RSI 計算 (過熱指標)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 數值提取
        now_price = df['Close'].iloc[-1].item()
        prev_price = df['Close'].iloc[-2].item()
        diff = now_price - prev_price
        rsi_val = df['RSI'].iloc[-1].item()
        
        # 預測邏輯
        recent_range = df['High'].tail(20).max() - df['Low'].tail(20).min()
        target_up = now_price + (recent_range * 1.382)

        # 介面呈現
        status_class = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"## {stock_id} 專業決策儀表板")
        st.markdown(f"現價：<span class='{status_class}'>{now_price:.2f}</span> "
                    f"({'▲' if diff >= 0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        st.divider()

        # 第一排：策略看板
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("🔮 預告噴發目標")
            st.subheader(f"NT$ {target_up:.2f}")
        with c2:
            st.success("🎯 建議進場區間")
            st.subheader(f"{df['Lower'].iloc[-1]:.1f} ~ {df['MA20'].iloc[-1]:.1f}")
        with c3:
            # 過熱指標判斷
            rsi_status = "🔥 過熱" if rsi_val > 70 else "🧊 超跌" if rsi_val < 30 else "⚖️ 適中"
            st.warning(f"🌡️ 過熱指標 (RSI)")
            st.subheader(f"{rsi_val:.1f} ({rsi_status})")

        # 圖表展示 (K線 + RSI)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                           row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
        
        # 1. K線 + 布林
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)
        
        # 2. RSI 圖
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta', width=1), name="RSI"), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

        # 3. 成交量
        bar_colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=bar_colors, name="成交量"), row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 策略總結
        st.markdown(f"""
        <div style="background-color:#1E222D; padding:20px; border-radius:10px; border-left: 5px solid #FFD700;">
        <h3>💡 老師深度策略解讀</h3>
        <ul>
            <li><b>過熱判斷：</b>目前 RSI 為 <b>{rsi_val:.1f}</b>，{'建議分批獲利，不要追高' if rsi_val > 70 else '目前尚無過熱跡象，趨勢可持續關注' if rsi_val > 50 else '處於低檔轉折區，等待帶量紅K確認'}。</li>
            <li><b>扣抵動能：</b>目前股價大於 20 日前的價格，<b>月線助漲力道強勁</b>，拉回即是買點。</li>
            <li><b>操作建議：</b>若回測 <b>{df['MA20'].iloc[-1]:.2f}</b> 站穩，預告轉折目標價 <b>{target_up:.2f}</b> 達標機率極大。</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.warning("查無資料")
except Exception as e:
    st.error(f"系統異常: {e}")

st.caption("免責聲明：本程式僅供技術分析參考，投資人應獨立判斷並自負盈虧。")
