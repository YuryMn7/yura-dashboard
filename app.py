import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h2 style='text-align: center; color: #333;'>Профессиональный Терминал Архитектора</h2>", unsafe_allow_html=True)

ASSETS = {
    "EUR/USD": "EURUSD=X", "USD/JPY": "USDJPY=X", "SPX500": "^GSPC", "GER40": "^GDAXI", 
    "JPN225": "^N225", "GBP/USD": "GBPUSD=X", "GBP/JPY": "GBPJPY=X", "AUD/USD": "AUDUSD=X", 
    "AUS200": "^AXJO", "EUR/JPY": "EURJPY=X", "EUR/AUD": "EURAUD=X", "NZD/USD": "NZDUSD=X", 
    "Золото": "GC=F", "Биткоин": "BTC-USD"
}
TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1"]

col1, col2 = st.columns(2)
with col1: asset_name = st.selectbox("Символ:", list(ASSETS.keys()), index=0)
with col2: tf = st.selectbox("Таймфрейм:", TIMEFRAMES, index=7) # H8 по умолчанию

ticker = ASSETS[asset_name]

@st.cache_data(ttl=60) # Кэширование сбережет наши лимиты!
def get_market_data(t, interval):
    yf_int = interval
    per = "2y"
    if interval == "M1": yf_int = "1m"; per = "7d"
    elif interval == "M5": yf_int = "5m"; per = "60d"
    elif interval in ["M15", "M30"]: yf_int = interval.lower(); per = "60d"
    elif interval in ["H1", "H2", "H4", "H8"]: yf_int = "1h"; per = "700d"
    elif interval == "D1": yf_int = "1d"; per = "10y"
    elif interval == "W1": yf_int = "1wk"; per = "15y"
    elif interval == "MN1": yf_int = "1mo"; per = "max"

    try:
        df = yf.download(t, period=per, interval=yf_int, progress=False)
        if df.empty: return df
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        if interval == "H2": df = df.resample('2h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        elif interval == "H4": df = df.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        elif interval == "H8": df = df.resample('8h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
        return df
    except: return pd.DataFrame()

df = get_market_data(ticker, tf)

if not df.empty:
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Prev_Close']), abs(df['Low'] - df['Prev_Close'])))
    df['ATR'] = df['TR'].rolling(14).mean()

    # --- СТРОГИЕ ФРАКТАЛЫ ---
    high, low = df['High'], df['Low']
    df['Minor_High'] = (high > high.shift(1)) & (high > high.shift(2)) & (high > high.shift(-1)) & (high > high.shift(-2))
    df['Minor_Low'] = (low < low.shift(1)) & (low < low.shift(2)) & (low < low.shift(-1)) & (low < low.shift(-2))
    
    df['Major_High'] = True
    df['Major_Low'] = True
    for i in range(1, 11):
        df['Major_High'] &= (high > high.shift(i)) & (high > high.shift(-i))
        df['Major_Low'] &= (low < low.shift(i)) & (low < low.shift(-i))

    df_plot = df.tail(250).copy()
    
    # 🛠 СЕКРЕТ ИДЕАЛЬНЫХ СВЕЧЕЙ: Отвязываем график от дат (X = 0, 1, 2...)
    df_plot['x_idx'] = np.arange(len(df_plot))

    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df_plot['x_idx'], # Строгая сетка без дыр!
        open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
        increasing_line_color='black', increasing_fillcolor='white',
        decreasing_line_color='black', decreasing_fillcolor='black',
        name='Цена'
    ))

    # Младшие Точки
    minor_highs = df_plot[df_plot['Minor_High'] & ~df_plot['Major_High']]
    fig.add_trace(go.Scatter(
        x=minor_highs['x_idx'], y=minor_highs['High'] + (minor_highs['ATR'] * 0.2),
        mode='markers', marker=dict(size=6, color='#888888', symbol='circle'), name='Младший Максимум'
    ))
    minor_lows = df_plot[df_plot['Minor_Low'] & ~df_plot['Major_Low']]
    fig.add_trace(go.Scatter(
        x=minor_lows['x_idx'], y=minor_lows['Low'] - (minor_lows['ATR'] * 0.2),
        mode='markers', marker=dict(size=6, color='#888888', symbol='circle'), showlegend=False
    ))

    # Старшие Точки
    major_highs = df_plot[df_plot['Major_High']]
    fig.add_trace(go.Scatter(
        x=major_highs['x_idx'], y=major_highs['High'] + (major_highs['ATR'] * 0.5),
        mode='markers', marker=dict(size=12, color='black', symbol='circle'), name='Старший Максимум'
    ))
    major_lows = df_plot[df_plot['Major_Low']]
    fig.add_trace(go.Scatter(
        x=major_lows['x_idx'], y=major_lows['Low'] - (major_lows['ATR'] * 0.5),
        mode='markers', marker=dict(size=12, color='black', symbol='circle'), showlegend=False
    ))

    # 🛠 СЕКРЕТ ИДЕАЛЬНОЙ ШКАЛЫ: Возвращаем даты только как подписи
    tick_step = max(1, len(df_plot) // 10)
    tick_vals = df_plot['x_idx'].values[::tick_step]
    tick_texts = df_plot.index.strftime('%d %b %H:%M')[::tick_step]

    fig.update_layout(
        xaxis_rangeslider_visible=False, 
        height=750, 
        template="plotly_white",
        plot_bgcolor='#fafafa', paper_bgcolor='white',
        margin=dict(l=20, r=60, t=30, b=30),
        yaxis=dict(side='right', tickformat='.5f', showgrid=True, gridcolor='#e1e1e1', zeroline=False, title='Цена'),
        xaxis=dict(
            tickmode='array', tickvals=tick_vals, ticktext=tick_texts, # Клеим даты на ровную сетку!
            showgrid=True, gridcolor='#e1e1e1', tickangle=0
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # 🛠 СЕКРЕТ ИДЕАЛЬНЫХ КОТИРОВОК: Принуждаем показывать 5 знаков при касании!
    fig.update_traces(yhoverformat=".5f")
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Нет данных от биржи.")
