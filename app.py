import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 頁面基本設定
st.set_page_config(page_title="江江老師風-專業轉折系統", layout="wide")

# 台股配色 CSS
st.markdown("""
    <style>
    .up { color: #FF0000; font-size: 45px; font-weight: bold; }
    .down { color: #00FF00; font-size: 45px; font-weight: bold; }
    .metric-label { font-size: 18px; color: #888; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.header("🚀 核心參數設定")
stock_id = st.sidebar.text_input("輸入台股代號", value="2330")

def get_data(symbol):
    # 嘗試上市櫃
    df = yf.download(f"{symbol}.TW", period="6mo", interval="1d")
    if df.empty:
        df = yf.download(f"{symbol}.TWO", period="6mo", interval="1d")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

try:
    df = get_data(stock_id)
    if not df.empty:
        # --- 技術指標計算 ---
        # 1. 布林通道
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD'] = df['Close'].rolling(window=20).std()
        df['Upper'] = df['MA20'] + (df['STD'] * 2)
        df['Lower'] = df['MA20'] - (df['STD'] * 2)
        
        # 2. 均線扣抵位置 (20天前與60天前)
        deduct_20_idx = -20
        deduct_60_idx = -60
        
        # 3. 預告轉折預測
        now_price = df['Close'].iloc[-1].item()
        prev_price = df['Close'].iloc[-2].item()
        diff = now_price - prev_price
        target_up = now_price + (df['High'].tail(20).max() - df['Low'].tail(20).min()) * 1.382

        # --- 畫面呈現 ---
        # 標題與現價
        status_color = "up" if diff >= 0 else "down"
        st.markdown(f"## {stock_id} 專業全方位決策看板")
        st.markdown(f"最新價：<span class='{status_color}'>{now_price:.2f}</span> "
                    f"({'▲' if diff >= 0 else '▼'}{abs(diff):.2f})", unsafe_allow_html=True)

        # 頂部指標卡
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🔮 預告目標價", f"{target_up:.2f}")
        c2.metric("🏠 布林中軌(MA20)", f"{df['MA20'].iloc[-1]:.2f}")
        c3.metric("☁️ 布林天線", f"{df['Upper'].iloc[-1]:.2f}")
        c4.metric("🕳️ 布林地線", f"{df['Lower'].iloc[-1]:.2f}")

        # --- 繪製多功能圖表 ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           row_heights=[0.7, 0.3], vertical_spacing=0.05)

        # K線圖
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], 
                                   low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        
        # 加上布林通道
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='rgba(255,255,255,0.2)'), name="天線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='rgba(255,255,255,0.2)'), fill='tonexty', name="地線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=1), name="月線(中軌)"), row=1, col=1)

        # 標註扣抵值位置 (畫一個圓點在20天前的K線上)
        deduct_date = df.index[deduct_20_idx]
        deduct_price = df['Close'].iloc[deduct_20_idx]
        fig.add_trace(go.Scatter(x=[deduct_date], y=[deduct_price], mode="markers+text",
                                text=["● 20日扣抵"], textposition="bottom center",
                                marker=dict(color="orange", size=12), name="扣抵點"), row=1, col=1)

        # 下方成交量
        bar_colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=bar_colors, name="成交量"), row=2, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 老師語錄分析
        st.info(f"💡 **江江觀點分析：** \n"
                f"1. **均線趨勢：** 目前股價({now_price:.2f}) {'高於' if now_price > deduct_price else '低於'} 扣抵價({deduct_price:.2f})，月線預計將{'持續上揚' if now_price > deduct_price else '開始走平或下彎'}。\n"
                f"2. **布林位置：** 股價目前位於布林{'高檔區' if now_price > df['Upper'].iloc[-1] else '整理區'}，請留意{'過熱回檔' if now_price > df['Upper'].iloc[-1] else '突破機會'}。")

    else:
        st.warning("查無資料")
except Exception as e:
    st.error(f"分析失敗: {e}")
