import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# 設定網頁
st.set_page_config(page_title="台股轉折觀測站", layout="wide")

# 側邊欄：輸入股票代號
st.sidebar.header("設定")
stock_input = st.sidebar.text_input("輸入台股代號 (如: 2330)", value="2330")
stock_id = f"{stock_input}.TW"

# 抓取數據
@st.cache_data(ttl=600) # 快取 10 分鐘，避免頻繁抓取
def get_data(ticker):
    df_min = yf.download(ticker, period="5d", interval="1m")
    df_day = yf.download(ticker, period="5d", interval="1d")
    return df_min, df_day

try:
    df_min, df_day = get_data(stock_id)
    
    if not df_day.empty:
        # 計算 CDP 轉折值
        last_day = df_day.iloc[-2] # 抓昨天的資料計算今日轉折
        H, L, C = last_day['High'].item(), last_day['Low'].item(), last_day['Close'].item()
        
        CDP = (H + L + 2 * C) / 4
        AH, NH = CDP + (H - L), 2 * CDP - L
        NL, AL = 2 * CDP - H, CDP - (H - L)

        # 顯示數值
        st.title(f"📈 {stock_input} 轉折值監測")
        cols = st.columns(5)
        titles = ["最高壓力(AH)", "近期壓力(NH)", "轉折重心(CDP)", "近期支撐(NL)", "最低支撐(AL)"]
        vals = [AH, NH, CDP, NL, AL]
        for col, t, v in zip(cols, titles, vals):
            col.metric(t, f"{v:.2f}")

        # 畫圖
        fig = go.Figure(data=[go.Candlestick(x=df_min.index, open=df_min['Open'], high=df_min['High'], low=df_min['Low'], close=df_min['Close'])])
        fig.update_layout(template="plotly_dark", height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("找不到股票資料，請檢查代號。")
except:
    st.error("讀取資料時發生錯誤。")
