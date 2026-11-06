import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import gc
from streamlit_plotly_events import plotly_events

API_KEY = "498c4e4630ab4727974c2ff5439be7dd"

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h3 style='text-align: center; color: #2c3e50;'>Ichimoku Wave Terminal</h3>", unsafe_allow_html=True)

if 'abc_points' not in st.session_state:
    st.session_state.abc_points = []

ASSETS = {
    "EUR/USD": "EUR/USD", "USD/JPY": "USD/JPY", "GBP/USD": "GBP/USD",
    "AUD/USD": "AUD/USD", "NZD/USD": "NZD/USD", "EUR/JPY": "EUR/JPY",
    "GBP/JPY": "GBP/JPY", "EUR/AUD": "EUR/AUD", 
    "XAU/USD (Gold)": "XAU/USD", "BTC/USD (Bitcoin)": "BTC/USD",
    "SPX500": "SPX", "GER40 (DAX)": "GDAXI", "JPN225": "N225"
}

TF_MAP = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H2": "2h", "H4": "4h", "D1": "1day", "W1": "1week", "MN1": "1month"}
KIHON_SUU = [9, 17, 26, 33, 42, 52]

with st.sidebar:
    st.header("Настройки")
    asset_name = st.selectbox("Символ:", list(ASSETS.keys()), index=0)
    tf_name = st.selectbox("Таймфрейм:", list(TF_MAP.keys()), index=4)
    
    st.markdown("---")
    st.write(f"**Точек волны:** {len(st.session_state.abc_points)}/3")
    if st.button("🗑 Очистить точки A-B-C", use_container_width=True):
        st.session_state.abc_points = []
        st.rerun()

ticker = ASSETS[asset_name]
td_interval = TF_MAP[tf_name]

@st.cache_data(ttl=60)
def fetch_twelvedata(symbol, interval):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={API_KEY}&outputsize=400"
    try:
        response = requests.get(url).json()
        if 'values' in response:
            df = pd.DataFrame(response['values'])
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()
            # 🛠 ОЧИСТКА МУСОРА: Удаляем дубликаты свечей!
            df = df[~df.index.duplicated(keep='last')]
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
    
    # 🛠 ИДЕАЛЬНЫЕ СВЕЧИ: Убрана жирная обводка (line_width=1)
    fig.add_trace(go.Candlestick(
        x=df_plot['x_idx'], open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'],
        increasing_line_color='#2c3e50', increasing_fillcolor='white', increasing_line_width=1,
        decreasing_line_color='#2c3e50', decreasing_fillcolor='#2c3e50', decreasing_line_width=1,
        name='Свечи'
    ))

    # Рисуем Фракталы
    minor_highs = df_plot[df_plot['Minor_High'] & ~df_plot['Major_High']]
    fig.add_trace(go.Scatter(x=minor_highs['x_idx'], y=minor_highs['High']+(minor_highs['ATR']*0.2), mode='markers', marker=dict(size=5, color='#95a5a6'), name='Minor High'))
    minor_lows = df_plot[df_plot['Minor_Low'] & ~df_plot['Major_Low']]
    fig.add_trace(go.Scatter(x=minor_lows['x_idx'], y=minor_lows['Low']-(minor_lows['ATR']*0.2), mode='markers', marker=dict(size=5, color='#95a5a6'), name='Minor Low'))
    
    major_highs = df_plot[df_plot['Major_High']]
    fig.add_trace(go.Scatter(x=major_highs['x_idx'], y=major_highs['High']+(major_highs['ATR']*0.5), mode='markers', marker=dict(size=10, color='#2c3e50'), name='Major High'))
    major_lows = df_plot[df_plot['Major_Low']]
    fig.add_trace(go.Scatter(x=major_lows['x_idx'], y=major_lows['Low']-(major_lows['ATR']*0.5), mode='markers', marker=dict(size=10, color='#2c3e50'), name='Major Low'))

    # Ишимоку
    fig.add_trace(go.Scatter(x=df_plot['x_idx'], y=df_plot['tenkan'], line=dict(color='#2980b9', width=1.5), name='Tenkan'))
    fig.add_trace(go.Scatter(x=df_plot['x_idx'], y=df_plot['kijun'], line=dict(color='#e74c3c', width=2), name='Kijun'))
    
    x_cloud = np.arange(26, len(df_plot) + 26)
    sa, sb = df_plot['raw_senkou_a'].values, df_plot['raw_senkou_b'].values
    fig.add_trace(go.Scatter(x=np.concatenate([x_cloud, x_cloud[::-1]]), y=np.concatenate([sa, sb[::-1]]), fill='toself', fillcolor='rgba(46, 204, 113, 0.2)', line=dict(color='rgba(255,255,255,0)'), name='Kumo'))

    # ==========================================
    # 4. ПОЛНЫЙ АРСЕНАЛ ВРЕМЕНИ И ЦЕЛЕЙ
    # ==========================================
    if len(st.session_state.abc_points) == 3:
        A, B, C = st.session_state.abc_points[0], st.session_state.abc_points[1], st.session_state.abc_points[2]
        is_up = B['y'] > A['y']
        
        # Математика Архитектора
        if is_up:
            V, N, E, NT = B['y'] + (B['y'] - C['y']), C['y'] + (B['y'] - A['y']), B['y'] + (B['y'] - A['y']), C['y'] + (C['y'] - A['y'])
        else:
            V, N, E, NT = B['y'] - (C['y'] - B['y']), C['y'] - (A['y'] - B['y']), B['y'] - (A['y'] - B['y']), C['y'] - (A['y'] - C['y'])

        colors = {'V': 'orange', 'N': 'green', 'E': 'red', 'NT': 'purple'}
        for name, val in {'V': V, 'N': N, 'E': E, 'NT': NT}.items():
            fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text=f"Цель {name}: {val:.5f}", annotation_position="right")

        # ⏳ МАГИЯ ВРЕМЕНИ (Все симметрии и Кихон Суу)
        time_AB = abs(B['x'] - A['x'])
        time_AC = abs(C['x'] - A['x'])
        
        fig.add_vline(x=C['x'] + time_AB, line_dash="dot", line_color="blue", annotation_text=f"Тайёсуу A-B ({int(time_AB)})")
        fig.add_vline(x=C['x'] + time_AC, line_dash="dot", line_color="teal", annotation_text=f"Тайёсуу A-C ({int(time_AC)})")
        
        for k in KIHON_SUU:
            fig.add_vline(x=C['x'] + k - 1, line_dash="dash", line_color="gray", annotation_text=f"Кихон ({k})", opacity=0.5)

        # Рисуем Волну
        fig.add_trace(go.Scatter(x=[A['x'], B['x'], C['x']], y=[A['y'], B['y'], C['y']], mode='lines+markers', line=dict(color='gold', width=3), marker=dict(size=10), name='Волна A-B-C'))

    tick_step = max(1, len(df_plot) // 10)
    tick_vals = df_plot['x_idx'].values[::tick_step]
    tick_texts = df_plot.index.strftime('%Y-%m-%d %H:%M')[::tick_step]

    # 🛠 СВОБОДНОЕ МАСШТАБИРОВАНИЕ (Без жестких рамок!)
    fig.update_layout(
        xaxis_rangeslider_visible=False, height=750, template="plotly_white",
        plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', margin=dict(l=20, r=80, t=40, b=40),
        yaxis=dict(side='right', tickformat='.5f', showgrid=True, gridcolor='#f0f0f0', fixedrange=False),
        xaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_texts, showgrid=True, gridcolor='#f0f0f0', tickangle=45, fixedrange=False),
        hovermode="closest", clickmode='event+select'
    )
    
    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points")
    
    if event and len(event.selection['points']) > 0:
        clicked_pt = event.selection['points'][0]
        clicked_x = clicked_pt.get('x')
        clicked_y = clicked_pt.get('y')
        
        if len(st.session_state.abc_points) < 3:
            already_exists = any(p['x'] == clicked_x for p in st.session_state.abc_points)
            if not already_exists and clicked_x is not None and clicked_y is not None:
                st.session_state.abc_points.append({'x': clicked_x, 'y': clicked_y})
                st.rerun()

    gc.collect()
else:
    st.warning("Нет данных от биржи.")
