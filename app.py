import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gc

# ==========================================
# 1. КОНФИГУРАЦИЯ ТЕРМИНАЛА
# ==========================================
API_KEY = "498c4e4630ab4727974c2ff5439be7dd"

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h2 style='text-align: center; color: #2c3e50;'>Ichimoku Analytical Terminal</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #7f8c8d;'>Professional Market Analysis Tool</p>", unsafe_allow_html=True)

# Профессиональные тикеры TwelveData (Форекс, Крипта, Индексы)
ASSETS = {
    "EUR/USD": "EUR/USD", "USD/JPY": "USD/JPY", "GBP/USD": "GBP/USD",
    "AUD/USD": "AUD/USD", "NZD/USD": "NZD/USD", "EUR/JPY": "EUR/JPY",
    "GBP/JPY": "GBP/JPY", "EUR/AUD": "EUR/AUD", 
    "XAU/USD (Gold)": "XAU/USD", "BTC/USD (Bitcoin)": "BTC/USD",
    "SPX500": "SPX", "GER40 (DAX)": "GDAXI", "JPN225": "N225"
}

# Таймфреймы TwelveData
TF_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H2": "2h", "H4": "4h", 
    "D1": "1day", "W1": "1week", "MN1": "1month"
}

# ==========================================
# 2. ИНТЕРФЕЙС УПРАВЛЕНИЯ
# ==========================================
st.sidebar.header("Market Parameters")
asset_name = st.sidebar.selectbox("Symbol:", list(ASSETS.keys()), index=0)
tf_name = st.sidebar.selectbox("Timeframe:", list(TF_MAP.keys()), index=4)

ticker = ASSETS[asset_name]
td_interval = TF_MAP[tf_name]

# ==========================================
# 3. ПОЛУЧЕНИЕ ДАННЫХ (API TWELVE DATA)
# ==========================================
@st.cache_data(ttl=60) # Кэш на 1 минуту для экономии API лимитов
def fetch_twelvedata(symbol, interval):
    # Запрашиваем 350 свечей, чтобы хватило и на Ишимоку, и на график
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={API_KEY}&outputsize=350"
    try:
        response = requests.get(url).json()
        if 'values' in response:
            df = pd.DataFrame(response['values'])
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()
            # Конвертируем строки в числа
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
            return df
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()

df = fetch_twelvedata(ticker, td_interval)

# ==========================================
# 4. ВЫЧИСЛЕНИЯ ИШИМОКУ И ФРАКТАЛОВ
# ==========================================
if not df.empty:
    # Волатильность (ATR)
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Prev_Close']), abs(df['Low'] - df['Prev_Close'])))
    df['ATR'] = df['TR'].rolling(14).mean()

    # Линии Ишимоку
    high, low, close = df['High'], df['Low'], df['Close']
    df["tenkan"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    df["kijun"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    df["raw_senkou_a"] = (df["tenkan"] + df["kijun"]) / 2
    df["raw_senkou_b"] = (high.rolling(52).max() + low.rolling(52).min()) / 2

    # Изолированные строгие фракталы
    df['Minor_High'] = (high > high.shift(1)) & (high > high.shift(2)) & (high > high.shift(-1)) & (high > high.shift(-2))
    df['Minor_Low'] = (low < low.shift(1)) & (low < low.shift(2)) & (low < low.shift(-1)) & (low < low.shift(-2))
    
    df['Major_High'] = True
    df['Major_Low'] = True
    for i in range(1, 11):
        df['Major_High'] &= (high > high.shift(i)) & (high > high.shift(-i))
        df['Major_Low'] &= (low < low.shift(i)) & (low < low.shift(-i))

    # ==========================================
    # 5. ВИЗУАЛИЗАЦИЯ (СТРОГИЙ ДИЗАЙН)
    # ==========================================
    # Ограничиваем отрисовку последними 250 свечами
    df_plot = df.tail(250).copy()
    df_plot['x_idx'] = np.arange(len(df_plot)) # Категорийная ось X (без дыр)

    fig = go.Figure()
    
    # Японские свечи
    fig.add_trace(go.Candlestick(
        x=df_plot['x_idx'],
        open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
        increasing_line_color='#2c3e50', increasing_fillcolor='white',
        decreasing_line_color='#2c3e50', decreasing_fillcolor='#2c3e50',
        name='Price'
    ))

    # Младшие Фракталы
    minor_highs = df_plot[df_plot['Minor_High'] & ~df_plot['Major_High']]
    fig.add_trace(go.Scatter(
        x=minor_highs['x_idx'], y=minor_highs['High'] + (minor_highs['ATR'] * 0.2),
        mode='markers', marker=dict(size=5, color='#95a5a6', symbol='circle'), name='Minor High'
    ))
    minor_lows = df_plot[df_plot['Minor_Low'] & ~df_plot['Major_Low']]
    fig.add_trace(go.Scatter(
        x=minor_lows['x_idx'], y=minor_lows['Low'] - (minor_lows['ATR'] * 0.2),
        mode='markers', marker=dict(size=5, color='#95a5a6', symbol='circle'), showlegend=False
    ))

    # Старшие Фракталы
    major_highs = df_plot[df_plot['Major_High']]
    fig.add_trace(go.Scatter(
        x=major_highs['x_idx'], y=major_highs['High'] + (major_highs['ATR'] * 0.5),
        mode='markers', marker=dict(size=10, color='#2c3e50', symbol='circle'), name='Major High'
    ))
    major_lows = df_plot[df_plot['Major_Low']]
    fig.add_trace(go.Scatter(
        x=major_lows['x_idx'], y=major_lows['Low'] - (major_lows['ATR'] * 0.5),
        mode='markers', marker=dict(size=10, color='#2c3e50', symbol='circle'), showlegend=False
    ))

    # Линии Ишимоку
    fig.add_trace(go.Scatter(x=df_plot['x_idx'], y=df_plot['tenkan'], line=dict(color='#2980b9', width=1.5), name='Tenkan-sen'))
    fig.add_trace(go.Scatter(x=df_plot['x_idx'], y=df_plot['kijun'], line=dict(color='#e74c3c', width=2), name='Kijun-sen'))
    
    # Chikou Span (Сдвинутая назад)
    fig.add_trace(go.Scatter(x=df_plot['x_idx'] - 26, y=df_plot['Close'], line=dict(color='#8e44ad', width=1.5, dash='dashdot'), name='Chikou Span'))

    # Облако Кумо (Проекция в будущее)
    x_cloud = np.arange(26, len(df_plot) + 26)
    sa = df_plot['raw_senkou_a'].values
    sb = df_plot['raw_senkou_b'].values
    
    fig.add_trace(go.Scatter(
        x=np.concatenate([x_cloud, x_cloud[::-1]]),
        y=np.concatenate([sa, sb[::-1]]),
        fill='toself',
        fillcolor='rgba(46, 204, 113, 0.2)', # Зеленое облако
        line=dict(color='rgba(255,255,255,0)'),
        showlegend=False,
        name='Kumo (Bullish)'
    ))

    # Шкала X (Даты)
    tick_step = max(1, len(df_plot) // 10)
    tick_vals = df_plot['x_idx'].values[::tick_step]
    tick_texts = df_plot.index.strftime('%Y-%m-%d %H:%M')[::tick_step]

    fig.update_layout(
        xaxis_rangeslider_visible=False, height=750, template="plotly_white",
        plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', margin=dict(l=20, r=60, t=40, b=40),
        yaxis=dict(side='right', tickformat='.5f', showgrid=True, gridcolor='#f0f0f0', zeroline=False, title='Price'),
        xaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_texts, showgrid=True, gridcolor='#f0f0f0', tickangle=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="closest"
    )
    fig.update_traces(yhoverformat=".5f")
    
    st.plotly_chart(fig, use_container_width=True)
    del fig
    gc.collect()

else:
    st.warning("Market data is currently unavailable or symbol is incorrect.")
