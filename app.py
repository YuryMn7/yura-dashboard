import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import yfinance as yf
import gc
from streamlit_plotly_events import plotly_events

# ==========================================
# 1. КОНФИГУРАЦИЯ ТЕРМИНАЛА
# ==========================================
API_KEY = "498c4e4630ab4727974c2ff5439be7dd"

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h3 style='text-align: center; color: #2c3e50;'>Ichimoku Wave Terminal</h3>", unsafe_allow_html=True)

if 'abc_points' not in st.session_state:
    st.session_state.abc_points = []

# 🗺 СМАРТ-МАРШРУТИЗАЦИЯ: Кому куда идти за данными
ASSET_ROUTER = {
    "EUR/USD": {"prov": "twelvedata", "sym": "EUR/USD"},
    "USD/JPY": {"prov": "twelvedata", "sym": "USD/JPY"},
    "GBP/USD": {"prov": "twelvedata", "sym": "GBP/USD"},
    "AUD/USD": {"prov": "twelvedata", "sym": "AUD/USD"},
    "NZD/USD": {"prov": "twelvedata", "sym": "NZD/USD"},
    "EUR/JPY": {"prov": "twelvedata", "sym": "EUR/JPY"},
    "GBP/JPY": {"prov": "twelvedata", "sym": "GBP/JPY"},
    "EUR/AUD": {"prov": "twelvedata", "sym": "EUR/AUD"},
    "Золото": {"prov": "twelvedata", "sym": "XAU/USD"},
    "Биткоин": {"prov": "twelvedata", "sym": "BTC/USD"},
    # Индексы забираем у Yahoo, так как TwelveData просит за них платную лицензию!
    "SPX500": {"prov": "yahoo", "sym": "^GSPC"},
    "GER40": {"prov": "yahoo", "sym": "^GDAXI"},
    "JPN225": {"prov": "yahoo", "sym": "^N225"},
    "AUS200": {"prov": "yahoo", "sym": "^AXJO"}
}

TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1"]
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]

with st.sidebar:
    st.header("Настройки")
    asset_name = st.selectbox("Символ:", list(ASSET_ROUTER.keys()), index=0)
    tf_name = st.selectbox("Таймфрейм:", TIMEFRAMES, index=4)
    
    st.markdown("---")
    st.write(f"**Точек волны:** {len(st.session_state.abc_points)}/3")
    if st.button("🗑 Очистить точки A-B-C", use_container_width=True):
        st.session_state.abc_points = []
        st.rerun()

# ==========================================
# 2. УМНЫЙ ДОБЫТЧИК ДАННЫХ
# ==========================================
@st.cache_data(ttl=60)
def fetch_smart_data(asset_key, interval):
    route = ASSET_ROUTER[asset_key]
    provider = route["prov"]
    sym = route["sym"]
    df = pd.DataFrame()
    
    try:
        if provider == "twelvedata":
            td_map = {"M1":"1min", "M5":"5min", "M15":"15min", "M30":"30min", "H1":"1h", "H2":"1h", "H4":"1h", "H8":"1h", "D1":"1day", "W1":"1week", "MN1":"1month"}
            url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval={td_map[interval]}&apikey={API_KEY}&outputsize=400"
            res = requests.get(url).json()
            if 'values' in res:
                df = pd.DataFrame(res['values'])
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime').sort_index()
                for col in ['open', 'high', 'low', 'close']: df[col] = df[col].astype(float)
                df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
                
        elif provider == "yahoo":
            yf_int = interval
            per = "2y"
            if interval == "M1": yf_int = "1m"; per = "5d"
            elif interval == "M5": yf_int = "5m"; per = "1mo"
            elif interval == "M15": yf_int = "15m"; per = "1mo"
            elif interval == "M30": yf_int = "30m"; per = "1mo"
            elif interval in ["H1", "H2", "H4", "H8"]: yf_int = "1h"; per = "700d"
            elif interval == "D1": yf_int = "1d"; per = "10y"
            elif interval == "W1": yf_int = "1wk"; per = "15y"
            elif interval == "MN1": yf_int = "1mo"; per = "max"
            
            df = yf.download(sym, period=per, interval=yf_int, progress=False)
            if not df.empty and isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)

        # ОБЩАЯ КУЗНИЦА ДЛЯ ОБОИХ ПРОВАЙДЕРОВ
        if not df.empty and interval in ["H2", "H4", "H8"]:
            if interval == "H2": df = df.resample('2h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            elif interval == "H4": df = df.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            elif interval == "H8": df = df.resample('8h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            
        return df
    except: return pd.DataFrame()

df = fetch_smart_data(asset_name, tf_name)

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
        increasing_line_width=1, decreasing_line_width=1, name='Свечи'
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
    # 4. МАГИЯ РАСЧЕТА ЦЕЛЕЙ (V, N, E, NT)
    # ==========================================
    if len(st.session_state.abc_points) == 3:
        A, B, C = st.session_state.abc_points[0], st.session_state.abc_points[1], st.session_state.abc_points[2]
        is_up = B['y'] > A['y']
        
        if is_up:
            V, N, E, NT = B['y'] + (B['y'] - C['y']), C['y'] + (B['y'] - A['y']), B['y'] + (B['y'] - A['y']), C['y'] + (C['y'] - A['y'])
        else:
            V, N, E, NT = B['y'] - (C['y'] - B['y']), C['y'] - (A['y'] - B['y']), B['y'] - (A['y'] - B['y']), C['y'] - (A['y'] - C['y'])

        colors = {'V': 'orange', 'N': 'green', 'E': 'red', 'NT': 'purple'}
        for name, val in {'V': V, 'N': N, 'E': E, 'NT': NT}.items():
            fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text=f"Цель {name}: {val:.5f}", annotation_position="right")

        time_AB = abs(B['x'] - A['x'])
        time_AC = abs(C['x'] - A['x'])
        
        fig.add_vline(x=C['x'] + time_AB, line_dash="dot", line_color="blue", annotation_text=f"Тайёсуу A-B ({int(time_AB)})")
        fig.add_vline(x=C['x'] + time_AC, line_dash="dot", line_color="teal", annotation_text=f"Тайёсуу A-C ({int(time_AC)})")
        
        for k in KIHON_SUU:
            fig.add_vline(x=C['x'] + k - 1, line_dash="dash", line_color="gray", annotation_text=f"Кихон ({k})", opacity=0.5)

        fig.add_trace(go.Scatter(x=[A['x'], B['x'], C['x']], y=[A['y'], B['y'], C['y']], mode='lines+markers', line=dict(color='gold', width=3), marker=dict(size=10), name='Волна A-B-C'))

    tick_step = max(1, len(df_plot) // 10)
    tick_vals = df_plot['x_idx'].values[::tick_step]
    tick_texts = df_plot.index.strftime('%Y-%m-%d %H:%M')[::tick_step]

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
