import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

st.set_page_config(page_title="專業級台股轉折觀測站", layout="wide")

# --- 側邊欄 ---
st.sidebar.header("🔍 股票搜尋")
stock_input = st.sidebar.text_input("輸入台股代號 (如: 2330 或 8069)", value="2330")

# --- 核心抓取邏輯 (自動判斷上市櫃) ---
def fetch_data(symbol):
    # 優先嘗試上市 (.TW)
    df = yf.download(f"{symbol}.TW", period="3mo", interval="1d")
    if df.empty:
        # 若無資料，嘗試上櫃 (.TWO)
        df = yf.download(f"{symbol}.TWO", period="3mo", interval="1d")
    return df

try:
    df = fetch_data(stock_input)
    
    if not df.empty:
        # 計算 CDP 轉折值 (使用最新一天的前一天)
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
        
        H, L, C = prev_row['High'].item(), prev_row['Low'].item(), prev_row['Close'].item()
        CDP = (H + L + 2 * C) / 4
        AH, NH = CDP + (H - L), 2 * CDP - L
        NL, AL = 2 * CDP - H, CDP - (H - L)

        # --- 顯示數據看板 ---
        st.title(f"📊 {stock_input} 行情與轉折分析")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("最高壓力(AH)", f"{AH:.2f}")
        m2.metric("近期壓力(NH)", f"{NH:.2f}")
        m3.metric("轉折重心(CDP)", f"{CDP:.2f}")
        m4.metric("近期支撐(NL)", f"{NL:.2f}")
        m5.metric("最低支撐(AL)", f"{AL:.2f}")

        st.divider()

        # --- 繪製 K 線 + 量能圖 ---
        # 建立兩個垂直排列的圖表 (K線佔 80%, 成交量佔 20%)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.03, row_heights=[0.7, 0.3])

        # 1. K線圖
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="K線"
        ), row=1, col=1)

        # 2. 成交量圖 (顏色區分紅漲綠跌)
        colors = ['#ef5350' if df['Close'][i] >= df['Open'][i] else '#26a69a' for i in range(len(df))]
        fig.add_trace(go.Bar(
            x=df.index, y=df['Volume'], name="成交量", marker_color=colors
        ), row=2, col=1)

        # 3. 加入 CDP 參考水平線 (僅畫在 K 線圖上)
        fig.add_hline(y=CDP, line_dash="dash", line_color="white", annotation_text="CDP", row=1, col=1)

        fig.update_layout(
            height=700, template="plotly_dark", showlegend=False,
            xaxis_rangeslider_visible=False,
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning(f"⚠️ 找不到代號 '{stock_input}' 的資料。請確認代號是否正確，或該股是否已下市。")

except Exception as e:
    st.error(f"發生程式錯誤: {e}")
