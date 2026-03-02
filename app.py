import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# 頁面基本設定
st.set_page_config(page_title="台股全方位預告系統", layout="wide")

# 台股紅綠燈 CSS
st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 50px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 50px; font-weight: bold; }
    .highlight-box { background-color: #1E222D; padding: 20px; border-radius: 10px; border-left: 5px solid #FFD700; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.header("📊 參數設定")
stock_id = st.sidebar.text_input("輸入台股代號", value="2330")

def get_data(symbol):
    df = yf.download(f"{symbol}.TW", period="8mo", interval="1d")
    if df.empty:
        df = yf.download(f"{symbol}.TWO", period="8mo", interval="1d")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

try:
    df = get_data(stock_id)
    if not df.empty:
        # --- 進階指標計算 ---
        # 1. 布林通道 & 月線
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD'] = df['Close'].rolling(window=20).std()
        df['Upper'] = df['MA20'] + (df['STD'] * 2)
        df['Lower'] = df['MA20'] - (df['STD'] * 2)
        
        # 2. ATR (平均真實波幅) - 計算預計天數用
        df['TR'] = np.maximum(df['High'] - df['Low'], 
                             np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                                      abs(df['Low'] - df['Close'].shift(1))))
        df['ATR'] = df['TR'].rolling(window=14).mean()
        
        # 3. 數值提取
        now_price = df['Close'].iloc[-1].item()
        prev_price = df['Close'].iloc[-2].item()
        diff = now_price - prev_price
        atr_val = df['ATR'].iloc[-1].item()
        
        # 4. 預告目標與轉折
        recent_range = df['High'].tail(20).max() - df['Low'].tail(20).min()
        target_up = now_price + (recent_range * 1.382)
        target_extreme = now_price + (recent_range * 1.618)
        
        # 5. 預估天數邏輯
        days_to_target = max(1, round((target_up - now_price) / (atr_val * 0.8))) # 假設動能 80%

        # --- 介面呈現 ---
        status_class = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"## {stock_id} 預告轉折與策略分析")
        st.markdown(f"現價：<span class='{status_class}'>{now_price:.2f}</span> "
                    f"({'▲' if diff >= 0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        # 核心策略區塊
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("🔮 預告噴發目標")
            st.subheader(f"NT$ {target_up:.2f}")
            st.write(f"預計達成：**{days_to_target} ~ {days_to_target+5}** 個交易日")
        with c2:
            st.success("🎯 建議進場區間")
            entry_low = df['Lower'].iloc[-1]
            entry_high = df['MA20'].iloc[-1]
            st.subheader(f"{entry_low:.1f} ~ {entry_high:.1f}")
            st.write("策略：回測月線或下軌不破布局")
        with c3:
            st.warning("⚠️ 極限轉折壓力")
            st.subheader(f"NT$ {target_extreme:.2f}")
            st.write("建議此位準採取分批獲利")

        # --- 圖表展示 ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        
        # K線 + 布林
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='gray', width=1, dash='dot'), name="天線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='gray', width=1, dash='dot'), name="地線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="月線"), row=1, col=1)

        # 標註目標線
        fig.add_hline(y=target_up, line_dash="dash", line_color="red", annotation_text="預告目標", row=1, col=1)
        
        # 成交量
        bar_colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=bar_colors, name="成交量"), row=2, col=1)

        fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- 策略總結 ---
        st.markdown(f"""
        <div class="highlight-box">
        <h3>💡 江江風格決策參考</h3>
        <ul>
            <li><b>趨勢：</b>目前月線{'上揚' if df['MA20'].iloc[-1] > df['MA20'].iloc[-5] else '下彎'}。多頭格局{'確認' if now_price > df['MA20'].iloc[-1] else '尚未站穩'}。</li>
            <li><b>時機：</b>若股價回落至 <b>{entry_high:.2f}</b> 附近出現長下影線，為最佳轉折買點。</li>
            <li><b>風險：</b>跌破 <b>{df['Lower'].iloc[-1]:.2f} (地線)</b> 則預告轉折失敗，需嚴格止損。</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.warning("請輸入正確的台股代號")
except Exception as e:
    st.error(f"分析異常: {e}")
