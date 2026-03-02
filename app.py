import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests

# 頁面基本設定
st.set_page_config(page_title="台股全能決策系統", layout="wide")

# 台股配色 CSS
st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 45px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 45px; font-weight: bold; }
    .recommend-card { background-color: #1E222D; padding: 12px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 10px; }
    .tag-chip { background-color: #FF5252; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; margin-right: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 側邊欄控制 ---
st.sidebar.header("🚀 系統設定")
stock_id = st.sidebar.text_input("輸入台股代號", value="2330")
use_chip_filter = st.sidebar.checkbox("🔒 僅推薦外資買超標的", value=False)

# --- 核心邏輯：資料抓取 (修正 MultiIndex) ---
def get_stock_data(symbol, period="8mo"):
    df = yf.download(f"{symbol}.TW", period=period, interval="1d", progress=False)
    if df.empty:
        df = yf.download(f"{symbol}.TWO", period=period, interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

# --- 核心邏輯：外資買超檢查 (FinMind 公開介面) ---
def check_foreign_buy(symbol):
    try:
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={symbol}"
        res = requests.get(url).json()
        df_chip = pd.DataFrame(res['data'])
        if not df_chip.empty:
            last_chip = df_chip[df_chip['name'] == 'Foreign_Investor'].iloc[-1]
            return last_chip['buy'] > last_chip['sell']
    except:
        return True # 介面異常時預設不阻擋
    return False

# --- 核心邏輯：全自動掃描器 ---
def run_stock_scanner(filter_chip):
    # 擴大掃描池：權值、AI、電力、航運等龍頭
    pool = ["2330", "2454", "2317", "2303", "2382", "3231", "1513", "1503", "2603", "2609", "2408", "2344", "3034", "3037", "2376", "6163", "2406"]
    valid_stocks = []
    
    for s in pool:
        try:
            d = get_stock_data(s, period="2mo")
            if len(d) < 40: continue
            
            c = d['Close'].iloc[-1].item()
            m5, m10, m20 = d['Close'].rolling(5).mean().iloc[-1], d['Close'].rolling(10).mean().iloc[-1], d['Close'].rolling(20).mean().iloc[-1]
            
            # 條件 1: 多頭排列 (現價 > 5 > 10 > 20)
            is_bull = c > m5 > m10 > m20
            # 條件 2: 扣三低 (現價大於 5, 10, 20 天前的價格)
            is_low_deduct = c > d['Close'].iloc[-5] and c > d['Close'].iloc[-10] and c > d['Close'].iloc[-20]
            # 條件 3: 戴維斯雙擊 (量增且收紅)
            is_davis = d['Volume'].iloc[-1] > d['Volume'].iloc[-2] * 1.1 and c > d['Open'].iloc[-1]
            
            if is_bull and is_low_deduct:
                if filter_chip:
                    if check_foreign_buy(s):
                        valid_stocks.append({"id": s, "type": "外資連敲" if is_davis else "多頭發動"})
                else:
                    valid_stocks.append({"id": s, "type": "雙擊發動" if is_davis else "扣三低"})
        except:
            continue
    return valid_stocks

# 側邊欄推薦顯示
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 老師嚴選：今日潛力股")
with st.sidebar:
    with st.spinner('AI 掃描中...'):
        picks = run_stock_scanner(use_chip_filter)
        if picks:
            for p in picks:
                st.markdown(f"""<div class='recommend-card'>
                            <b>{p['id']}</b> <span class='tag-chip'>{p['type']}</span>
                            </div>""", unsafe_allow_html=True)
        else:
            st.write("目前無符合強勢標的")
st.sidebar.caption("※ 掃描依據：扣三低、多頭排列、外資動向")

# --- 主畫面儀表板 (延續前版邏輯) ---
try:
    df = get_stock_data(stock_id)
    if not df.empty:
        # 技術指標與目標價計算 (略，同前版但包含 RSI 與預估天數)
        now_price = df['Close'].iloc[-1].item()
        prev_price = df['Close'].iloc[-2].item()
        diff = now_price - prev_price
        
        # 繪圖與呈現...
        st.title(f"📈 {stock_id} 預告轉折全功能看板")
        status = "up-price" if diff >= 0 else "down-price"
        st.markdown(f"最新價：<span class='{status}'>{now_price:.2f}</span>", unsafe_allow_html=True)
        
        # (此處可貼上上一版的主圖表與策略總結邏輯)
        # 為了節省空間，請將上一版的 fig 繪製部分保留在此處
        st.info("💡 貼心提示：側邊欄已加入選股過濾，您可以勾選『外資買超』來過濾出法人的心頭好。")
    else:
        st.warning("請輸入正確代號")
except Exception as e:
    st.error(f"分析異常: {e}")
