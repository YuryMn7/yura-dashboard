import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import yfinance as yf
import gc
from streamlit_plotly_events import plotly_events

API_KEY = st.secrets["TWELVEDATA_KEY"]

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h3 style='text-align: center; color: #2c3e50;'>Ichimoku Wave Terminal</h3>", unsafe_allow_html=True)

if 'abc_points' not in st.session_state:
    st.session_state.abc_points = []

# --- СЛОВАРИ АКТИВОВ И МАРШРУТИЗАТОРЫ ---
ASSET_ROUTER = {
    "EUR/USD": {"prov": "twelvedata", "sym": "EUR/USD", "yf": "EURUSD=X"},
    "USD/JPY": {"prov": "twelvedata", "sym": "USD/JPY", "yf": "USDJPY=X"},
    "GBP/USD": {"prov": "twelvedata", "sym": "GBP/USD", "yf": "GBPUSD=X"},
    "AUD/USD": {"prov": "twelvedata", "sym": "AUD/USD", "yf": "AUDUSD=X"},
    "NZD/USD": {"prov": "twelvedata", "sym": "NZD/USD", "yf": "NZDUSD=X"},
    "EUR/JPY": {"prov": "twelvedata", "sym": "EUR/JPY", "yf": "EURJPY=X"},
    "GBP/JPY": {"prov": "twelvedata", "sym": "GBP/JPY", "yf": "GBPJPY=X"},
    "EUR/AUD": {"prov": "twelvedata", "sym": "EUR/AUD", "yf": "EURAUD=X"},
    "Золото": {"prov": "twelvedata", "sym": "XAU/USD", "yf": "GC=F"},
    "Биткоин": {"prov": "twelvedata", "sym": "BTC/USD", "yf": "BTC-USD"},
    "SPX500": {"prov": "yahoo", "sym": "^GSPC", "yf": "^GSPC"},
    "GER40": {"prov": "yahoo", "sym": "^GDAXI", "yf": "^GDAXI"},
    "JPN225": {"prov": "yahoo", "sym": "^N225", "yf": "^N225"},
    "AUS200": {"prov": "yahoo", "sym": "^AXJO", "yf": "^AXJO"}
}

TF_MAP = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h", "D1": "1day", "W1": "1week", "MN1": "1month"}
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]

# --- ФУНКЦИИ ИШИМОКУ ---
def calc_ichi(df):
    high, low, close = df['High'], df['Low'], df['Close']
    df["tenkan"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    df["kijun"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    df["raw_senkou_a"] = (df["tenkan"] + df["kijun"]) / 2
    df["raw_senkou_b"] = (high.rolling(52).max() + low.rolling(52).min()) / 2
    df["senkou_a"] = df["raw_senkou_a"].shift(26)
    df["senkou_b"] = df["raw_senkou_b"].shift(26)
    df["chikou"] = close.shift(-26)
    prev_close = close.shift(1)
    df['atr'] = np.maximum(high - low, np.maximum(abs(high - prev_close), abs(low - prev_close))).rolling(14).mean()
    return df

# ==========================================
# 🚀 ВКЛАДКИ САЙТА
# ==========================================
tab_radar, tab_terminal = st.tabs(["📡 Глобальный Радар", "📈 Терминал Архитектора"])

# ==========================================
# 📡 ВКЛАДКА 1: РАДАР (Работает через Yahoo)
# ==========================================
with tab_radar:
    st.markdown("### 📡 Сканирование всего рынка")
    st.write("Радар использует высокоскоростные потоки данных для мгновенного обзора 14 активов.")
    
    radar_tf = st.selectbox("Выберите таймфрейм для Радара:", ["M15", "M30", "H1", "H4", "D1"], index=2)
    
    if st.button("🚀 ЗАПУСТИТЬ СКАНИРОВАНИЕ РЫНКА", use_container_width=True):
        progress_text = "Гонцы сканируют рынки..."
        my_bar = st.progress(0, text=progress_text)
        
        radar_results = []
        htf_radar = TF_MAP[radar_tf] # Узнаем старший ТФ
        if radar_tf in ["M15", "M30"]: htf_radar = "H4"
        elif radar_tf in ["H1", "H2"]: htf_radar = "D1"
        elif radar_tf in ["H4", "H8"]: htf_radar = "W1"
        elif radar_tf == "D1": htf_radar = "MN1"
        
        total_assets = len(ASSET_ROUTER)
        
        for i, (r_name, route) in enumerate(ASSET_ROUTER.items()):
            my_bar.progress((i + 1) / total_assets, text=f"Анализирую {r_name}...")
            yf_sym = route["yf"]
            
            try:
                # Скачиваем через Yahoo для скорости (БЕЗ ЛИМИТОВ)
                per_ltf = "60d" if radar_tf in ["M15", "M30"] else "700d"
                per_htf = "700d" if htf_radar in ["H4", "D1"] else "15y"
                int_ltf = radar_tf.lower() if radar_tf in ["M15", "M30"] else ("1h" if "H" in radar_tf else "1d")
                int_htf = "1h" if htf_radar == "H4" else ("1d" if htf_radar == "D1" else ("1wk" if htf_radar == "W1" else "1mo"))
                
                df_ltf = yf.download(yf_sym, period=per_ltf, interval=int_ltf, progress=False)
                df_htf = yf.download(yf_sym, period=per_htf, interval=int_htf, progress=False)
                
                if df_ltf.empty or df_htf.empty: continue
                if isinstance(df_ltf.columns, pd.MultiIndex): df_ltf.columns = df_ltf.columns.get_level_values(0)
                if isinstance(df_htf.columns, pd.MultiIndex): df_htf.columns = df_htf.columns.get_level_values(0)
                
                # Кузница H4
                if radar_tf == "H4": df_ltf = df_ltf.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
                if htf_radar == "H4": df_htf = df_htf.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
                
                df_ltf = calc_ichi(df_ltf)
                df_htf = calc_ichi(df_htf)
                
                h_c = df_htf.iloc[-2]
                is_bull = float(h_c["Close"]) > max(float(h_c["senkou_a"]), float(h_c["senkou_b"])) and float(h_c["tenkan"]) >= float(h_c["kijun"])
                is_bear = float(h_c["Close"]) < min(float(h_c["senkou_a"]), float(h_c["senkou_b"])) and float(h_c["tenkan"]) <= float(h_c["kijun"])
                
                trend = "🟢 БЫЧИЙ" if is_bull else ("🔴 МЕДВЕЖИЙ" if is_bear else "➖ ФЛЭТ")
                
                l_c, p_b = df_ltf.iloc[-2], df_ltf.iloc[-28]
                pr, kijun = float(l_c["Close"]), float(l_c["kijun"])
                near = abs(pr - kijun) <= (float(l_c["atr"]) * 0.3)
                
                c_buy = pr > float(p_b["High"]) and pr > max(float(p_b["senkou_a"]), float(p_b["senkou_b"]))
                c_sell = pr < float(p_b["Low"]) and pr < min(float(p_b["senkou_a"]), float(p_b["senkou_b"]))
                
                bull = (float(l_c["tenkan"]) > kijun) and (pr > max(float(l_c["senkou_a"]), float(l_c["senkou_b"]))) and c_buy
                bear = (float(l_c["tenkan"]) < kijun) and (pr < min(float(l_c["senkou_a"]), float(l_c["senkou_b"]))) and c_sell
                
                sig = "🟢 ПОКУПКА" if near and is_bull and bull else ("🔴 ПРОДАЖА" if near and is_bear and bear else "⏳ Ждем")
                
                radar_results.append({"Актив": r_name, "Старший Тренд": trend, "Сигнал (Окоп)": sig, "Цена": f"{pr:.5f}"})
            except: pass
            
        my_bar.empty()
        
        # Вывод красивой таблицы
        if radar_results:
            df_res = pd.DataFrame(radar_results)
            st.dataframe(df_res, use_container_width=True, hide_index=True)
        else:
            st.warning("Не удалось просканировать рынки.")


# ==========================================
# 📈 ВКЛАДКА 2: ТЕРМИНАЛ (Работает через TwelveData)
# ==========================================
with tab_terminal:
    with st.sidebar:
        st.header("Настройки Терминала")
        asset_name = st.selectbox("Символ:", list(ASSET_ROUTER.keys()), index=0)
        tf_name = st.selectbox("Таймфрейм:", list(TF_MAP.keys()), index=4)
        
        st.markdown("---")
        st.markdown("### 🎯 Точки Волны (A-B-C)")
        
        labels = ["A (Старт)", "B (Вершина/Дно)", "C (Откат)"]
        for i in range(3):
            if i < len(st.session_state.abc_points):
                val = st.session_state.abc_points[i]['y']
                st.success(f"**Точка {labels[i]}:** {val:.5f}")
            else:
                st.info(f"Ожидаю точку {labels[i]}...")
                
        if st.button("🗑 Очистить точки", use_container_width=True):
            st.session_state.abc_points = []
            st.rerun()

    @st.cache_data(ttl=60)
    def fetch_smart_data(asset_key, interval):
        route = ASSET_ROUTER[asset_key]
        provider, sym = route["prov"], route["sym"]
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
                    df = df[~df.index.duplicated(keep='last')]
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
                if not df.empty and isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            if not df.empty and interval in ["H2", "H4", "H8"]:
                if interval == "H2": df = df.resample('2h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
                elif interval == "H4": df = df.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
                elif interval == "H8": df = df.resample('8h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            return df
        except: return pd.DataFrame()

    df = fetch_smart_data(asset_name, tf_name)

    if not df.empty:
        df = calc_ichi(df)

        high, low = df['High'], df['Low']
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

        minor_highs = df_plot[df_plot['Minor_High'] & ~df_plot['Major_High']]
        fig.add_trace(go.Scatter(x=minor_highs['x_idx'], y=minor_highs['High']+(minor_highs['ATR']*0.2), mode='markers', marker=dict(size=5, color='#95a5a6'), name='Minor High'))
        minor_lows = df_plot[df_plot['Minor_Low'] & ~df_plot['Major_Low']]
        fig.add_trace(go.Scatter(x=minor_lows['x_idx'], y=minor_lows['Low']-(minor_lows['ATR']*0.2), mode='markers', marker=dict(size=5, color='#95a5a6'), name='Minor Low'))
        
        major_highs = df_plot[df_plot['Major_High']]
        fig.add_trace(go.Scatter(x=major_highs['x_idx'], y=major_highs['High']+(major_highs['ATR']*0.5), mode='markers', marker=dict(size=10, color='#2c3e50'), name='Major High'))
        major_lows = df_plot[df_plot['Major_Low']]
        fig.add_trace(go.Scatter(x=major_lows['x_idx'], y=major_lows['Low']-(major_lows['ATR']*0.5), mode='markers', marker=dict(size=10, color='#2c3e50'), name='Major Low'))

        fig.add_trace(go.Scatter(x=df_plot['x_idx'], y=df_plot['tenkan'], line=dict(color='#2980b9', width=1.5), name='Tenkan'))
        fig.add_trace(go.Scatter(x=df_plot['x_idx'], y=df_plot['kijun'], line=dict(color='#e74c3c', width=2), name='Kijun'))
        
        x_cloud = np.arange(26, len(df_plot) + 26)
        sa, sb = df_plot['raw_senkou_a'].values, df_plot['raw_senkou_b'].values
        fig.add_trace(go.Scatter(x=np.concatenate([x_cloud, x_cloud[::-1]]), y=np.concatenate([sa, sb[::-1]]), fill='toself', fillcolor='rgba(46, 204, 113, 0.2)', line=dict(color='rgba(255,255,255,0)'), name='Kumo'))

        # МАГИЯ РАСЧЕТА ЦЕЛЕЙ (V, N, E, NT)
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

            time_AB, time_AC = abs(B['x'] - A['x']), abs(C['x'] - A['x'])
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
            plot_bgcolor='#ffffff', paper_bgcolor='#ffffff', margin=dict(l=20, r=80, t=40, b=80),
            yaxis=dict(side='right', tickformat='.5f', showgrid=True, gridcolor='#f0f0f0', fixedrange=False),
            xaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_texts, showgrid=True, gridcolor='#f0f0f0', tickangle=45, fixedrange=False),
            hovermode="closest", clickmode='event+select', dragmode="pan", font=dict(color='#2c3e50'),
            legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
        )
        
        event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", config={"scrollZoom": False, "displayModeBar": True}, theme=None)
        
        if event and len(event.selection['points']) > 0:
            clicked_pt = event.selection['points'][0]
            clicked_x = clicked_pt.get('x')
            clicked_y = clicked_pt.get('y')
            
            if len(st.session_state.abc_points) < 3:
                already_exists = any(p['x'] == clicked_x for p in st.session_state.abc_points)
                if not already_exists and clicked_x is not None and clicked_y is not None:
                    # Корректируем клик: если ткнули чуть выше/ниже, берем точный Хай или Лоу свечи!
                    exact_price = df_plot.loc[df_plot['x_idx'] == clicked_x, 'High'].values[0] if len(st.session_state.abc_points) == 1 else df_plot.loc[df_plot['x_idx'] == clicked_x, 'Low'].values[0]
                    st.session_state.abc_points.append({'x': clicked_x, 'y': exact_price})
                    st.rerun()

        gc.collect()
    else:
        st.warning("Нет данных от биржи.")
