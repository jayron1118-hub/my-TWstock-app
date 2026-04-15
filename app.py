import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
from datetime import datetime

# 1. 頁面配置與專業深色介面
st.set_page_config(page_title="台股全能轉折預告系統 - 擬像超越版", layout="wide")

st.markdown("""
    <style>
    .up-price { color: #FF0000; font-size: 42px; font-weight: bold; }
    .down-price { color: #00FF00; font-size: 42px; font-weight: bold; }
    .analysis-box { background-color: #1E222D; padding: 15px; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 10px; }
    .metric-card { background-color: #161A25; padding: 10px; border-radius: 8px; border: 1px solid #363C4E; text-align: center; }
    .recommend-card { background-color: #161A25; padding: 12px; border-radius: 8px; border: 1px solid #363C4E; margin-bottom: 8px; }
    .tag-chip { background-color: #FF5252; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 核心邏輯：功能函數 ---
def calculate_cdp(df):
    if df.empty: return None
    last = df.iloc[-1]
    H, L, C = last['High'].item(), last['Low'].item(), last['Close'].item()
    cdp = (H + L + 2 * C) / 4
    return {"AH": cdp + (H - L), "NH": 2 * cdp - L, "CDP": cdp, "NL": 2 * cdp - H, "AL": cdp - (H - L)}

@st.cache_data(ttl=600)
def get_stock_data(user_input, is_index=False):
    symbol = user_input.strip()
    ticker = symbol if is_index else f"{symbol}.TW"
    df = yf.download(ticker, period="1y", interval="1d", progress=False)
    if not is_index and df.empty:
        df = yf.download(f"{symbol}.TWO", period="1y", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def is_foreign_buying(symbol):
    try:
        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={symbol}"
        res = requests.get(url).json()
        df_chip = pd.DataFrame(res['data'])
        if not df_chip.empty:
            last = df_chip[df_chip['name'] == 'Foreign_Investor'].iloc[-1]
            return (last['buy'] - last['sell']) > 0
    except: return True
    return False

# --- 新增邏輯：進階分析 ---
def analyze_k_lines(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(last['Close'] - last['Open'])
    avg_body = abs(df['Close'] - df['Open']).tail(20).mean()
    
    patterns = []
    # 簡單 K 線形態辨識
    if last['Close'] > last['Open'] and last['Open'] < prev['Close'] < last['Close'] and body > avg_body:
        patterns.append("紅K吞噬 (多頭強勢)")
    elif last['Close'] < last['Open'] and last['Open'] > prev['Close'] > last['Close'] and body > avg_body:
        patterns.append("黑K吞噬 (空頭轉折)")
    if body < (avg_body * 0.2):
        patterns.append("十字星 (趨勢猶豫)")
    if (last['High'] - max(last['Open'], last['Close'])) > body * 2:
        patterns.append("上影線 (壓力顯現)")
    if (min(last['Open'], last['Close']) - last['Low']) > body * 2:
        patterns.append("下影線 (支撐強勁)")
    return patterns if patterns else ["盤整形態"]

def analyze_123_rule(df):
    # 簡化 123 法則：1. 破趨勢線 2. 測試高/低點不破 3. 突破前高/低
    # 以 20 日高低點為基準
    recent = df.tail(20)
    high_20 = recent['High'].max()
    low_20 = recent['Low'].min()
    now = df['Close'].iloc[-1]
    
    if now > df['MA20'].iloc[-1] and now > df['High'].iloc[-5]:
        return "123法則：多頭確認 (符合突破)"
    elif now < df['MA20'].iloc[-1] and now < df['Low'].iloc[-5]:
        return "123法則：空頭確認 (破位下殺)"
    return "123法則：觀察期 (趨勢未明)"

def analyze_divergence(df):
    # 量價背離：價漲量縮 or 價跌量增
    price_change = df['Close'].iloc[-1] > df['Close'].iloc[-5]
    vol_change = df['Volume'].iloc[-1] > df['Volume'].rolling(5).mean().iloc[-1]
    
    if price_change and not vol_change:
        return "⚠️ 量價背離：價漲量縮 (動能不足)"
    if not price_change and vol_change:
        return "⚠️ 量價背離：價跌量增 (恐慌拋售)"
    return "✅ 量價配合正常"

# --- 側邊欄 ---
st.sidebar.header("📊 系統監測")
search_input = st.sidebar.text_input("輸入代號 (如: 2330)", value="2330")

# 庫存試算
st.sidebar.subheader("💰 個人庫存試算")
cost_p = st.sidebar.number_input("平均成本", value=0.0)
stock_q = st.sidebar.number_input("持有股數", value=0)

# 大盤 CDP
st.sidebar.markdown("---")
taiex_df = get_stock_data("^TWII", is_index=True)
taiex_cdp = calculate_cdp(taiex_df)
if taiex_cdp:
    st.sidebar.subheader("📉 大盤未來轉折")
    st.sidebar.markdown(f"<div class='cdp-mini'>重心: {taiex_cdp['CDP']:.0f}<br><span style='color:red'>壓力: {taiex_cdp['AH']:.0f}</span> | <span style='color:green'>支撐: {taiex_cdp['AL']:.0f}</span></div>", unsafe_allow_html=True)

# --- 主畫面 ---
try:
    df = get_stock_data(search_input)
    if not df.empty:
        # 技術指標計算
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        # 預測未來均線 (基於目前扣抵位)
        koudi_20 = df['Close'].iloc[-20]
        future_ma20_slope = "上揚" if df['Close'].iloc[-1] > koudi_20 else "下彎"
        
        # MACD
        df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['DIF'] = df['EMA12'] - df['EMA26']
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['DIF'] - df['DEA']
        
        # 預告邏輯
        now_price = df['Close'].iloc[-1]
        atr = (df['High']-df['Low']).rolling(14).mean().iloc[-1]
        target_price = now_price + (df['High'].tail(20).max() - df['Low'].tail(20).min()) * 1.382
        
        # 顯示
        st.title(f"🚀 {search_input} 擬像轉折分析系統")
        cols = st.columns(4)
        cols[0].metric("現價", f"{now_price:.2f}")
        cols[1].metric("🔮 預告目標", f"{target_price:.2f}")
        cols[2].metric("🌙 月線預測", future_ma20_slope)
        cols[3].metric("📊 MACD 狀態", "金叉" if df['DIF'].iloc[-1] > df['DEA'].iloc[-1] else "死叉")

        # 深度分析看板
        st.subheader("🕵️ 進階技術診斷")
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown(f"<div class='analysis-box'><b>K線形態：</b><br>{' / '.join(analyze_k_lines(df))}</div>", unsafe_allow_html=True)
        with a2:
            st.markdown(f"<div class='analysis-box'><b>趨勢評估：</b><br>{analyze_123_rule(df)}</div>", unsafe_allow_html=True)
        with a3:
            st.markdown(f"<div class='analysis-box'><b>量價關係：</b><br>{analyze_divergence(df)}</div>", unsafe_allow_html=True)

        # 繪圖
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.4, 0.15, 0.15, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="MA20"), row=1, col=1)
        # 預測未來均線方向 (箭頭示意)
        fig.add_annotation(x=df.index[-1], y=df['MA20'].iloc[-1], text="▲" if future_ma20_slope=="上揚" else "▼", showarrow=False, font=dict(color="red" if future_ma20_slope=="上揚" else "green", size=20))
        
        # RSI/Volume/MACD 略 (與前版相同但整合進 4 層)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量"), row=3, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD柱"), row=4, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['DIF'], line=dict(color='white'), name="DIF"), row=4, col=1)
        
        fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 江江語錄升級
        st.success(f"💡 **擬像超越決策建議**：\n"
                   f"- **123法則：** 目前處於 {analyze_123_rule(df)}，操作需配合量價確認。\n"
                   f"- **未來均線：** 20日扣抵值為 {koudi_20:.2f}，現價在其之上，月線將持續保持 {future_ma20_slope} 態勢。\n"
                   f"- **MACD：** 柱狀體目前為 {'紅柱' if df['MACD_Hist'].iloc[-1] > 0 else '綠柱'}，動能仍有待觀察。")
    else: st.warning("請輸入正確代號")
except Exception as e: st.error(f"分析失敗: {e}")
