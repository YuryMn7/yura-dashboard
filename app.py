import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import gc

API_KEY = st.secrets["TWELVEDATA_KEY"]

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h3 style='text-align: center; color: #2c3e50;'>Ichimoku Wave Terminal</h3>", unsafe_allow_html=True)

if "abc_points" not in st.session_state:
    st.session_state.abc_points = []

# 1. ПОЛНЫЙ АРСЕНАЛ (ВКЛЮЧАЯ AUS200)
ASSETS = {
    "EUR/USD": "EUR/USD", "USD/JPY": "USD/JPY", "GBP/USD": "GBP/USD",
    "AUD/USD": "AUD/USD", "NZD/USD": "NZD/USD", "EUR/JPY": "EUR/JPY",
    "GBP/JPY": "GBP/JPY", "EUR/AUD": "EUR/AUD", "XAU/USD (Gold)": "XAU/USD",
    "BTC/USD (Bitcoin)": "BTC/USD", "SPX500": "SPX", "GER40 (DAX)": "GDAXI", 
    "JPN225": "N225", "AUS200": "AUS200"
}
YAHOO_SYMBOLS = {"SPX": "^GSPC", "GDAXI": "^GDAXI", "N225": "^N225", "AUS200": "^AXJO"}

# 2. НОВЫЕ ТАЙМФРЕЙМЫ (H8, MN6, MN24)
TF_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h",
    "D1": "1day", "W1": "1week", "MN1": "1month", 
    "MN6": "6month", "MN24": "24month"
}

KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]

def server_offset_hours(choice):
    if choice == "UTC+2": return 2
    if choice == "UTC+3": return 3
    if choice == "UTC": return 0
    zone = ZoneInfo("Europe/Bucharest")
    return int(datetime.now(zone).utcoffset().total_seconds() // 3600)

def fmt_price(price):
    if price >= 1000: return f"{price:.2f}"
    if price >= 10: return f"{price:.3f}"
    return f"{price:.5f}"

# 3. ДОБЫЧА И ОЧИСТКА ДАННЫХ
@st.cache_data(ttl=60)
def fetch_smart_data(asset_key, interval):
    sym = ASSETS[asset_key]
    is_yahoo = sym in YAHOO_SYMBOLS
    df = pd.DataFrame()
    
    try:
        if is_yahoo:
            ysym = YAHOO_SYMBOLS[sym]
            per = "2y"
            y_int = "1d"
            if interval == "M1": y_int = "1m"; per = "7d"
            elif interval in ["M5", "M15", "M30"]: y_int = interval.lower(); per = "60d"
            elif interval in ["H1", "H2", "H4", "H8"]: y_int = "1h"; per = "700d"
            elif interval == "D1": y_int = "1d"; per = "10y"
            elif interval == "W1": y_int = "1wk"; per = "15y"
            elif interval in ["MN1", "MN6", "MN24"]: y_int = "1mo"; per = "max"
            
            df = yf.download(ysym, period=per, interval=y_int, progress=False)
            if df.empty: return pd.DataFrame()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.rename(columns=lambda x: x.capitalize())
            if getattr(df.index, "tz", None) is None: df.index = df.index.tz_localize("UTC")
            else: df.index = df.index.tz_convert("UTC")
            
        else:
            base_int = TF_MAP[interval]
            if interval in ["H2", "H4", "H8"]: base_int = "1h"
            elif interval in ["MN6", "MN24"]: base_int = "1month"
            
            url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval={base_int}&apikey={API_KEY}&outputsize=5000"
            res = requests.get(url).json()
            if 'values' in res:
                df = pd.DataFrame(res['values'])
                df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
                df = df.set_index('datetime').sort_index()
                for col in ['open', 'high', 'low', 'close']: df[col] = pd.to_numeric(df[col], errors="coerce")
                df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
                df = df.dropna()

        # КУЗНИЦА ДЛЯ НЕСТАНДАРТНЫХ ТАЙМФРЕЙМОВ
        if not df.empty:
            if interval == "H2": df = df.resample('2h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            elif interval == "H4": df = df.resample('4h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            elif interval == "H8": df = df.resample('8h').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            elif interval == "MN6": df = df.resample('6MS').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            elif interval == "MN24": df = df.resample('24MS').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}).dropna()
            
            # Удаляем мусорные свечи
            df = df[(df["High"] >= df["Low"]) & (df["Close"] > 0)]
            
        return df
    except: return pd.DataFrame()

def forex_session(df_utc, offset, drop_weekend, drop_clearing, is_fx_flag):
    if df_utc.empty or not is_fx_flag or not (drop_weekend or drop_clearing): return df_utc
    minutes = np.asarray(df_utc.index.hour * 60 + df_utc.index.minute)
    dow = np.asarray(df_utc.index.dayofweek)
    closed = np.zeros(len(df_utc), dtype=bool)
    if drop_weekend:
        close_min = ((24 - offset) % 24) * 60
        closed = (dow == 5) | ((dow == 4) & (minutes >= close_min)) | ((dow == 6) & (minutes < close_min))
    if drop_clearing and offset != 0:
        break_min = ((23 - offset) % 24) * 60
        closed = closed | ((minutes >= break_min) & (minutes < break_min + 60))
    return df_utc.iloc[np.flatnonzero(~closed)]

with st.sidebar:
    st.header("Настройки")
    asset_name = st.selectbox("Символ:", list(ASSETS.keys()), index=0)
    tf_name = st.selectbox("Таймфрейм:", list(TF_MAP.keys()), index=4)
    offset_choice = st.selectbox("Время сервера MT5", ["Авто (EET)", "UTC+2", "UTC+3", "UTC"], index=0)
    count_weekend = st.checkbox("Считать субботу и ночь закрытия", value=False)
    drop_clearing = st.checkbox("Убирать час клиринга 23:00", value=False)
    offset = server_offset_hours(offset_choice)
    
    st.markdown("---")
    st.write(f"Точек волны: {len(st.session_state.abc_points)}/3")
    if st.button("Очистить точки A-B-C", use_container_width=True):
        st.session_state.abc_points = []
        st.rerun()
    labels = ["A (Старт)", "B (Вершина/Дно)", "C (Откат)"]
    for i in range(3):
        if i < len(st.session_state.abc_points): st.success(f"Точка {labels[i]}: {fmt_price(st.session_state.abc_points[i]['y'])}")
        else: st.info(f"Ожидаю {labels[i]}")

# ==========================================
# 4. РАСЧЕТ И ОТРИСОВКА
# ==========================================
df_raw = fetch_smart_data(asset_name, tf_name)
is_fx_flag = ("/" in ASSETS[asset_name]) and ("BTC" not in ASSETS[asset_name])

if tf_name not in ["W1", "MN1", "MN6", "MN24"]:
    df_raw = forex_session(df_raw, offset, not count_weekend, drop_clearing, is_fx_flag)
    if not df_raw.empty:
        df_raw.index = df_raw.index.tz_convert(timezone(timedelta(hours=offset))).tz_localize(None)
elif getattr(df_raw.index, "tz", None) is not None:
    df_raw.index = df_raw.index.tz_localize(None)

if not df_raw.empty:
    df = df_raw.copy()
    prev = df['Close'].shift(1)
    df['ATR'] = pd.concat([df['High']-df['Low'], (df['High']-prev).abs(), (df['Low']-prev).abs()], axis=1).max(axis=1).rolling(14).mean()
    
    high, low = df['High'], df['Low']
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
    df_plot["x_idx"] = np.arange(len(df_plot))

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_plot["x_idx"], open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
        increasing_line_color="#2c3e50", increasing_fillcolor="white", increasing_line_width=1,
        decreasing_line_color="#2c3e50", decreasing_fillcolor="#2c3e50", decreasing_line_width=1, name="Свечи"
    ))

    # Точки
    for mask, col, sign, factor, size, color, name in [
        (df_plot["Minor_High"] & ~df_plot["Major_High"], "High", 1, 0.2, 5, "#95a5a6", "Младший Максимум"),
        (df_plot["Minor_Low"] & ~df_plot["Major_Low"], "Low", -1, 0.2, 5, "#95a5a6", "Младший Минимум"),
        (df_plot["Major_High"], "High", 1, 0.5, 10, "#2c3e50", "Старший Максимум"),
        (df_plot["Major_Low"], "Low", -1, 0.5, 10, "#2c3e50", "Старший Минимум")
    ]:
        d = df_plot[mask]
        if not d.empty:
            y = d[col] + sign * d["ATR"].fillna(0) * factor
            custom = np.column_stack([d[col].to_numpy(), np.full(len(d), "H" if sign==1 else "L")])
            fig.add_trace(go.Scatter(x=d["x_idx"], y=y, mode="markers", marker=dict(size=size, color=color), name=name, customdata=custom, hovertemplate="%{customdata[0]:.5f}<extra></extra>"))

    fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["tenkan"], line=dict(color="#2980b9", width=1.5), name="Tenkan"))
    fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["kijun"], line=dict(color="#e74c3c", width=2), name="Kijun"))
    fig.add_trace(go.Scatter(x=df_plot["x_idx"] - 26, y=df_plot["Close"], line=dict(color="#1e8449", width=1.2), name="Chikou"))

    # ☁️ ИДЕАЛЬНОЕ ОБЛАКО: ОБЪЕДИНЕНО В ОДНУ КНОПКУ ЛЕГЕНДЫ!
    x_cloud = np.arange(len(df_plot)) + 26
    sa, sb = df_plot["raw_senkou_a"].to_numpy(dtype=float), df_plot["raw_senkou_b"].to_numpy(dtype=float)
    
    # Невидимый пустой график для красивой легенды
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", fill="toself", fillcolor="rgba(128,128,128,0.3)", line=dict(width=0), name="Kumo (Облако)", legendgroup="cloud"))
    
    i, n = 0, len(sa)
    while i < n:
        if not (np.isfinite(sa[i]) and np.isfinite(sb[i])): i += 1; continue
        is_up = bool(sa[i] >= sb[i])
        j = i + 1
        while j < n and np.isfinite(sa[j]) and np.isfinite(sb[j]) and bool(sa[j] >= sb[j]) == is_up: j += 1
        end = j + 1 if j < n and np.isfinite(sa[j]) and np.isfinite(sb[j]) else j
        if end - i >= 2:
            xs, ys = np.concatenate([x_cloud[i:end], x_cloud[i:end][::-1]]), np.concatenate([sa[i:end], sb[i:end][::-1]])
            color = "rgba(46, 204, 113, 0.35)" if is_up else "rgba(231, 76, 60, 0.28)"
            # Привязываем куски облака к группе "cloud" и прячем их из легенды
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=color, line=dict(width=0), showlegend=False, legendgroup="cloud", hoverinfo="skip"))
        i = j

    # ЦЕЛИ
    if len(st.session_state.abc_points) == 3:
        A, B, C = st.session_state.abc_points
        is_up = B["y"] > A["y"]
        if is_up: V, N, E, NT = B["y"] + (B["y"] - C["y"]), C["y"] + (B["y"] - A["y"]), B["y"] + (B["y"] - A["y"]), C["y"] + (C["y"] - A["y"])
        else: V, N, E, NT = B["y"] - (C["y"] - B["y"]), C["y"] - (A["y"] - B["y"]), B["y"] - (A["y"] - B["y"]), C["y"] - (A["y"] - C["y"])
        
        colors = {"V": "orange", "N": "green", "E": "red", "NT": "purple"}
        for name, val in {"V": V, "N": N, "E": E, "NT": NT}.items():
            fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text=f"Цель {name}: {fmt_price(val)}", annotation_position="right")
        
        time_ab, time_ac = abs(B["x"] - A["x"]), abs(C["x"] - A["x"])
        fig.add_vline(x=C["x"] + time_ab, line_dash="dot", line_color="blue", annotation_text=f"Тайёсуу A-B ({int(time_ab)})")
        fig.add_vline(x=C["x"] + time_ac, line_dash="dot", line_color="teal", annotation_text=f"Тайёсуу A-C ({int(time_ac)})")
        
        for k in KIHON_SUU:
            fig.add_vline(x=C["x"] + k - 1, line_dash="dash", line_color="gray", annotation_text=f"Кихон ({k})", opacity=0.35)
            
        fig.add_trace(go.Scatter(x=[A["x"], B["x"], C["x"]], y=[A["y"], B["y"], C["y"]], mode="lines+markers", line=dict(color="gold", width=3), marker=dict(size=10), name="Волна A-B-C"))

    tick_step = max(1, len(df_plot) // 10)
    fig.update_layout(
        xaxis_rangeslider_visible=False, height=750, template="plotly_white",
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", 
        margin=dict(l=20, r=80, t=40, b=80), # 🛠 Увеличили нижнее поле (b=80), чтобы дать место кнопкам
        yaxis=dict(side="right", tickformat=".5f", showgrid=True, gridcolor="#f0f0f0", fixedrange=False),
        xaxis=dict(tickmode="array", tickvals=df_plot["x_idx"].to_numpy()[::tick_step], ticktext=df_plot.index.strftime("%d %b %H:%M")[::tick_step], showgrid=True, gridcolor="#f0f0f0", tickangle=45, fixedrange=False),
        hovermode="closest", clickmode="event+select", dragmode="pan",
        font=dict(color='#2c3e50'),
        
        # 🛠 ИДЕАЛЬНАЯ ЛЕГЕНДА: Убираем её под график по центру!
        legend=dict(
            orientation="h", 
            yanchor="top", y=-0.15, # Опускаем ниже оси X
            xanchor="center", x=0.5   # Ставим ровно по центру
        )
    )
    
    # 🛠 ОТКЛЮЧАЕМ ВМЕШАТЕЛЬСТВО СТРИМЛИТА В ДИЗАЙН (theme=None)
    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", config={"scrollZoom": False, "displayModeBar": True}, theme=None)
    if event and event.selection and event.selection.get("points"):
        clicked = event.selection["points"][0]
        curve = clicked.get("curveNumber", clicked.get("curve_number"))
        custom = clicked.get("customdata")
        x_val = clicked.get("x")
        
        price = None
        if x_val is not None:
            rows = df_plot.loc[df_plot["x_idx"] == x_val]
            if not rows.empty:
                row = rows.iloc[0]
                kind = str(custom[1]) if isinstance(custom, (list, tuple)) and len(custom) >= 2 else None
                if kind == "H" or curve in (1, 3): price = float(row["High"])
                elif kind == "L" or curve in (2, 4): price = float(row["Low"])
                elif curve == 0:
                    y_val = clicked.get("y")
                    price = float(row["High"]) if y_val is None or abs(float(y_val)-row["High"]) <= abs(float(y_val)-row["Low"]) else float(row["Low"])

        if price is not None and x_val is not None:
            if len(st.session_state.abc_points) < 3:
                if not any(p["x"] == x_val for p in st.session_state.abc_points):
                    st.session_state.abc_points.append({"x": x_val, "y": price})
                    st.rerun()

else:
    st.warning("Нет данных. Проверьте подключение к API.")
