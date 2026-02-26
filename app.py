import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="台股轉折觀測站-修復版", layout="wide")

# 側邊欄控制
st.sidebar.header("🔍 股票搜尋")
stock_input = st.sidebar.text_input("輸入台股代號 (如: 2330)", value="2330")

# --- 核心抓取邏輯 (修正 MultiIndex 問題) ---
def fetch_data(symbol):
    # 嘗試抓取上市或上櫃
    df = yf.download(f"{symbol}.TW", period="3mo", interval="1d")
    if df.empty:
        df = yf.download(f"{symbol}.TWO", period="3mo", interval="1d")
    
    # 【關鍵修復】如果 yfinance 回傳多重索引，將其扁平化
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    return df

try:
    df = fetch_data(stock_input)
    
    if not df.empty:
        # 計算 CDP 轉折值
        prev_row = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
        H, L, C = prev_row['High'], prev_row['Low'], prev_row['Close']
        
        CDP = (H + L + 2 * C) / 4
        AH, NH = CDP + (H - L), 2 * CDP - L
        NL, AL = 2 * CDP - H, CDP - (H - L)

        st.title(f"📊 {stock_input} 行情監測")

        # 1. 轉折值看板
        cols = st.columns(5)
        titles = ["最高壓力(AH)", "近期壓力(NH)", "轉折重心(CDP)", "近期支撐(NL)", "最低支撐(AL)"]
        vals = [AH, NH, CDP, NL, AL]
        for col, t, v in zip(cols, titles, vals):
            col.metric(t, f"{v:.2f}")

        # 2. 繪製 K 線 + 成交量 (修正繪圖邏輯)
        # 建立子圖：1樓 K線, 2樓 成交量
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, 
                           row_heights=[0.7, 0.3])

        # 加入 K 線圖
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="K線"
        ), row=1, col=1)

        # 加入成交量圖 (使用 Bar)
        # 顏色邏輯：收盤 > 開盤 為紅(漲)，否則為綠(跌)
        bar_colors = ['red' if close >= open else 'green' 
                      for open, close in zip(df['Open'], df['Close'])]
        
        fig.add_trace(go.Bar(
            x=df.index, y=df['Volume'], 
            name="成交量",
            marker_color=bar_colors,
            opacity=0.8
        ), row=2, col=1)

        # 設定圖表樣式
        fig.update_layout(
            height=700,
            template="plotly_dark",
            xaxis_rangeslider_visible=False, # 關閉下方的縮放條
            margin=dict(t=50, b=50, l=50, r=50),
            hovermode='x unified'
        )
        
        # 隱藏成交量圖的縮放條
        fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
        fig.update_xaxes(rangeslider_visible=False, row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)

        # 3. 偵錯資訊 (如果圖還是跑不出來，可以看這裡)
        with st.expander("🛠️ 數據檢查 (若圖表消失請展開)"):
            st.write("最新 5 筆成交量數據：")
            st.write(df['Volume'].tail())

    else:
        st.warning(f"查無 '{stock_input}' 資料，請確認代號。")

except Exception as e:
    st.error(f"程式發生錯誤: {e}")
    
