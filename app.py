import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gc
from streamlit_plotly_events import plotly_events

# ==========================================
# 1. КОНФИГУРАЦИЯ ТЕРМИНАЛА
# ==========================================
API_KEY = "498c4e4630ab4727974c2ff5439be7dd"

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h2 style='text-align: center; color: #2c3e50;'>Ichimoku Analytical Terminal</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #7f8c8d;'>Interactive Wave & Time Targeting</p>", unsafe_allow_html=True)

# Инициализация памяти для точек A, B, C
if 'abc_points' not in st.session_state:
    st.session_state.abc_points = []

ASSETS = {
    "EUR/USD": "EUR/USD", "USD/JPY": "USD/JPY", "GBP/USD": "GBP/USD",
    "AUD/USD": "AUD/USD", "NZD/USD": "NZD/USD", "EUR/JPY": "EUR/JPY",
    "GBP/JPY": "GBP/JPY", "EUR/AUD": "EUR/AUD", 
    "XAU/USD (Gold)": "XAU/USD", "BTC/USD (Bitcoin)": "BTC/USD",
    "SPX500": "SPX", "GER40 (DAX)": "GDAXI", "JPN225": "N225"
}

TF_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H2": "2h", "H4": "4h", 
    "D1": "1day", "W1": "1week", "MN1": "1month"
}
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]

col1, col2, col3 = st.columns([2, 2, 1])
with col1: asset_name = st.selectbox("Символ:", list(ASSETS.keys()), index=0)
with col2: tf_name = st.selectbox("Таймфрейм:", list(TF_MAP.keys()), index=4)
with col3: 
    st.write("")
    st.write("")
    if st.button("🗑 Очистить точки A-B-C"):
        st.session_state.abc_points = []
        st.rerun()

ticker = ASSETS[asset_name]
td_interval = TF_MAP[tf_name]

# ==========================================
# 2. ПОЛУЧЕНИЕ ДАННЫХ
# ==========================================
@st.cache_data(ttl=60)
def fetch_twelvedata(symbol, interval):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={API_KEY}&outputsize=350"
    try:
        response = requests.get(url).json()
        if 'values' in response:
            df = pd.DataFrame(response['values'])
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()
            for col in ['open', 'high', 'low', 'close']: df[col] = df[col].astype(float)
            df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

df = fetch_twelvedata(ticker, td_interval)

if not df.empty:
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Prev_Close']), abs(df['Low'] - df['Prev_Close'])))
    df['ATR'] = df['TR'].rolling(14).mean()

    high, low, close = df['High'], df['Low'], df['Close']
    df["tenkan"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    df["kijun"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    df["raw_senkou_a"] = (df["tenkan"] + df["kijun"]) / 2
    df["raw_senkou_b"] = (high.rolling(52).max() + low.rolling(52).min()) / 2

    # Фракталы
    df['Minor_High'] = (high > high.shift(1)) & (high > high.shift(2)) & (high > high.shift(-1)) & (high > high.shift(-2))
    df['Minor_Low'] = (low < low.shift(1)) & (low < low.shift(2)) & (low < low.shift(-1)) & (low < low.shift(-2))
    
    df['Major_High'], df['Major_Low'] = True, True
    for i in range(1, 11):
        df['Major_High'] &= (high > high.shift(i)) & (high > high.shift(-i))
        df['Major_Low'] &= (low < low.shift(i)) & (low < low.shift(-i))

    df_plot = df.tail(250).copy()
    df_plot['x_idx'] = np.arange(len(df_plot))

    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=df_plot['x_idx'], open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
        increasing_line_color='#2c3e50', increasing_fillcolor='white', decreasing_line_color='#2c3e50', decreasing_fillcolor='#2c3e50',
        name='Price'
    ))

    # Рисуем Фракталы (делаем их кликабельными)
    minor_highs = df_plot[df_plot['Minor_High'] & ~df_plot['Major_High']]
    fig.add_trace(go.Scatter(x=minor_highs['x_idx'], y=minor_highs['High']+(minor_highs['ATR']*0.2), mode='markers', marker=dict(size=6, color='#95a5a6'), name='Minor High'))
    minor_lows = df_plot[df_plot['Minor_Low'] & ~df_plot['Major_Low']]
    fig.add_trace(go.Scatter(x=minor_lows['x_idx'], y=minor_lows['Low']-(minor_lows['ATR']*0.2), mode='markers', marker=dict(size=6, color='#95a5a6'), name='Minor Low'))
    
    major_highs = df_plot[df_plot['Major_High']]
    fig.add_trace(go.Scatter(x=major_highs['x_idx'], y=major_highs['High']+(major_highs['ATR']*0.5), mode='markers', marker=dict(size=12, color='#2c3e50'), name='Major High'))
    major_lows = df_plot[df_plot['Major_Low']]
    fig.add_trace(go.Scatter(x=major_lows['x_idx'], y=major_lows['Low']-(major_lows['ATR']*0.5), mode='markers', marker=dict(size=12, color='#2c3e50'), name='Major Low'))

    # Ишимоку
    fig.add_trace(go.Scatter(x=df_plot['x_idx'], y=df_plot['tenkan'], line=dict(color='#2980b9', width=1.5), name='Tenkan'))
    fig.add_trace(go.Scatter(x=df_plot['x_idx'], y=df_plot['kijun'], line=dict(color='#e74c3c', width=2), name='Kijun'))
    
    x_cloud = np.arange(26, len(df_plot) + 26)
    sa, sb = df_plot['raw_senkou_a'].values, df_plot['raw_senkou_b'].values
    fig.add_trace(go.Scatter(x=np.concatenate([x_cloud, x_cloud[::-1]]), y=np.concatenate([sa, sb[::-1]]), fill='toself', fillcolor='rgba(46, 204, 113, 0.2)', line=dict(color='rgba(255,255,255,0)'), name='Kumo'))

    # ==========================================
    # 3. МАГИЯ РАСЧЕТА ЦЕЛЕЙ (V, N, E, NT)
    # ==========================================
    if len(st.session_state.abc_points) == 3:
        A, B, C = st.session_state.abc_points[0], st.session_state.abc_points[1], st.session_state.abc_points[2]
        
        # Определяем тренд (B > A = Бычий, B < A = Медвежий)
        is_up = B['y'] > A['y']
        
        # Формулы Архитектора Юры
        if is_up:
            V = B['y'] + (B['y'] - C['y'])
            N = C['y'] + (B['y'] - A['y'])
            E = B['y'] + (B['y'] - A['y'])
            NT = C['y'] + (C['y'] - A['y'])
        else:
            V = B['y'] - (C['y'] - B['y'])
            N = C['y'] - (A['y'] - B['y'])
            E = B['y'] - (A['y'] - B['y'])
            NT = C['y'] - (A['y'] - C['y'])

        # Рисуем Горизонтальные Цели (Цены)
        colors = {'V': 'orange', 'N': 'green', 'E': 'red', 'NT': 'purple'}
        targets = {'V': V, 'N': N, 'E': E, 'NT': NT}
        
        for name, val in targets.items():
            fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text=f"Цель {name}: {val:.5f}", annotation_position="right")

        # Формулы Времени (Тайёсуу и Кихон Суу)
        time_AB = abs(B['x'] - A['x'])
        target_time = C['x'] + time_AB # Симметрия времени от С
        
        fig.add_vline(x=target_time, line_dash="dot", line_color="blue", annotation_text=f"Время Тайёсуу ({time_AB} бар)")

        # Рисуем треугольник волны
        fig.add_trace(go.Scatter(x=[A['x'], B['x'], C['x']], y=[A['y'], B['y'], C['y']], mode='lines+markers', line=dict(color='gold', width=3), marker=dict(size=10), name='Волна A-B-C'))

    # Настройки
    tick_step = max(1, len(df_plot) // 10)
    tick_vals = df_plot['x_idx'].values[::tick_step]
    tick_texts = df_plot.index.strftime('%Y-%m-%d %H:%M')[::tick_step]

    fig.update_layout(
        xaxis_rangeslider_visible=False, height=750, template="plotly_white",
        plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', margin=dict(l=20, r=80, t=40, b=40),
        yaxis=dict(side='right', tickformat='.5f', showgrid=True, gridcolor='#f0f0f0'),
        xaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_texts, showgrid=True, gridcolor='#f0f0f0'),
        hovermode="closest"
    )
    
    # 👆 ПЕРЕХВАТЧИК КЛИКОВ (Магия Streamlit)
    selected_points = plotly_events(fig, click_event=True, hover_event=False)
    
    # Обработка клика
    if selected_points:
        clicked_x = selected_points[0]['x']
        clicked_y = selected_points[0]['y']
        
        # Если точек меньше 3, добавляем новую
        if len(st.session_state.abc_points) < 3:
            # Корректируем Y, так как мы отступали точки от свечей на ATR
            actual_y = df_plot[df_plot['x_idx'] == clicked_x]['High'].values[0] if len(st.session_state.abc_points) == 1 else df_plot[df_plot['x_idx'] == clicked_x]['Low'].values[0]
            # Но для простоты пока берем просто координату клика
            st.session_state.abc_points.append({'x': clicked_x, 'y': clicked_y})
            st.rerun() # Перезагружаем страницу, чтобы нарисовать цели!

    # Показываем статус точек
    pts = st.session_state.abc_points
    status = "🔸 " + " ➔ ".join([f"({p['x']}, {p['y']:.5f})" for p in pts])
    if len(pts) < 3: st.info(f"Кликни на график, чтобы выбрать точки A, B, C. Выбрано: {len(pts)}/3\n{status}")
    else: st.success(f"Волна построена! {status}")

    gc.collect()
else:
    st.warning("Нет данных.")
