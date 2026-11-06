import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")

st.markdown("<h2 style='text-align: center; color: #333;'>Ichimoku Analytical Terminal</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>Профессиональная среда анализа рынков (Без выходных дыр)</p>", unsafe_allow_html=True)

# --- 1. ПОЛНЫЙ АРСЕНАЛ ИНСТРУМЕНТОВ ---
ASSETS = {
    "EUR/USD": "EURUSD=X", "USD/JPY": "USDJPY=X", "SPX500": "^GSPC", "GER40": "^GDAXI", 
    "JPN225": "^N225", "GBP/USD": "GBPUSD=X", "GBP/JPY": "GBPJPY=X", "AUD/USD": "AUDUSD=X", 
    "AUS200": "^AXJO", "EUR/JPY": "EURJPY=X", "EUR/AUD": "EURAUD=X", "NZD/USD": "NZDUSD=X", 
    "Золото": "GC=F", "Биткоин": "BTC-USD"
}

TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1"]

st.sidebar.header("Параметры анализа")
asset_name = st.sidebar.selectbox("Символ:", list(ASSETS.keys()))
tf = st.sidebar.selectbox("Таймфрейм:", TIMEFRAMES, index=4) # По умолчанию H1

ticker = ASSETS[asset_name]
st.write(f"Загрузка и переплавка данных: **{asset_name}** [{tf}]...")

# --- 2. КУЗНИЦА ТАЙМФРЕЙМОВ ---
@st.cache_data(ttl=60) # Кэшируем на 1 минуту, чтобы сайт летал
def get_market_data(t, interval):
    yf_int = interval
    per = "2y"
    if interval == "M1": yf_int = "1m"; per = "7d" # Yahoo дает минутки только за 7 дней
    elif interval == "M5": yf_int = "5m"; per = "60d"
    elif interval in ["M15", "M30"]: yf_int = interval.lower(); per = "60d"
    elif interval in ["H1", "H2", "H4", "H8"]: yf_int = "1h"; per = "700d"
    elif interval == "D1": yf_int = "1d"; per = "10y"
    elif interval == "W1": yf_int = "1wk"; per = "15y"
    elif interval == "MN1": yf_int = "1mo"; per = "max"

    df = yf.download(t, period=per, interval=yf_int, progress=False)
    if df.empty: return df
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    if interval == "H2": df = df.resample('2h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif interval == "H4": df = df.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    elif interval == "H8": df = df.resample('8h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
    return df

df = get_market_data(ticker, tf)

if not df.empty:
    # --- 3. МАТЕМАТИКА ЭКСТРЕМУМОВ И ВЕСА ---
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Prev_Close']), abs(df['Low'] - df['Prev_Close'])))
    df['ATR'] = df['TR'].rolling(14).mean()

    df['Minor_High'] = df['High'] == df['High'].rolling(5, center=True).max()
    df['Minor_Low'] = df['Low'] == df['Low'].rolling(5, center=True).min()
    
    df['Major_High'] = df['High'] == df['High'].rolling(21, center=True).max()
    df['Major_Low'] = df['Low'] == df['Low'].rolling(21, center=True).min()

    # Берем последние 250 свечей для идеальной детализации (чтобы не сжимать график)
    df_plot = df.tail(250).copy()
    
    # 🛠 СЕКРЕТ ИНЖЕНЕРА: Убираем дыры выходных дней!
    # Превращаем время в строчки, чтобы Plotly не пытался рисовать пустоту
    time_labels = df_plot.index.strftime('%Y-%m-%d %H:%M')

    # --- 4. РИСОВАНИЕ ---
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=time_labels, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
        increasing_line_color='black', increasing_fillcolor='white',
        decreasing_line_color='black', decreasing_fillcolor='black',
        name='Цена'
    ))

    # Рисуем Младшие точки
    minor_highs = df_plot[df_plot['Minor_High'] & ~df_plot['Major_High']]
    fig.add_trace(go.Scatter(
        x=minor_highs.index.strftime('%Y-%m-%d %H:%M'), 
        y=minor_highs['High'] + (minor_highs['ATR'] * 0.3),
        mode='markers', marker=dict(size=5, color='gray', symbol='circle'), name='Младший Экстремум'
    ))
    minor_lows = df_plot[df_plot['Minor_Low'] & ~df_plot['Major_Low']]
    fig.add_trace(go.Scatter(
        x=minor_lows.index.strftime('%Y-%m-%d %H:%M'), 
        y=minor_lows['Low'] - (minor_lows['ATR'] * 0.3),
        mode='markers', marker=dict(size=5, color='gray', symbol='circle'), showlegend=False
    ))

    # Рисуем Старшие точки
    major_highs = df_plot[df_plot['Major_High']]
    fig.add_trace(go.Scatter(
        x=major_highs.index.strftime('%Y-%m-%d %H:%M'), 
        y=major_highs['High'] + (major_highs['ATR'] * 0.6),
        mode='markers', marker=dict(size=10, color='black', symbol='circle'), name='Старший Экстремум'
    ))
    major_lows = df_plot[df_plot['Major_Low']]
    fig.add_trace(go.Scatter(
        x=major_lows.index.strftime('%Y-%m-%d %H:%M'), 
        y=major_lows['Low'] - (major_lows['ATR'] * 0.6),
        mode='markers', marker=dict(size=10, color='black', symbol='circle'), showlegend=False
    ))

    fig.update_layout(
        xaxis_rangeslider_visible=False, 
        height=700, 
        template="plotly_white",
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis=dict(type='category', nticks=10) # <-- Это заклинание сжимает график, убирая дыры!
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Нет данных от биржи (возможно, неторговое время или мало истории).")
