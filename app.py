import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import gc
import time

API_KEY = st.secrets["TWELVEDATA_KEY"]

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h3 style='text-align: center; color: #2c3e50;'>Ichimoku Wave Terminal</h3>", unsafe_allow_html=True)

if "abc_points" not in st.session_state:
    st.session_state.abc_points = []

# ==========================================
# 1. КОНСТАНТЫ И СЛОВАРИ
# ==========================================
ASSETS = {
    "EUR/USD": "EUR/USD", "USD/JPY": "USD/JPY", "GBP/USD": "GBP/USD",
    "AUD/USD": "AUD/USD", "NZD/USD": "NZD/USD", "EUR/JPY": "EUR/JPY",
    "GBP/JPY": "GBP/JPY", "EUR/AUD": "EUR/AUD", "XAU/USD (Gold)": "XAU/USD",
    "BTC/USD (Bitcoin)": "BTC/USD", "SPX500": "SPX", "GER40 (DAX)": "GDAXI",
    "JPN225": "N225", "AUS200": "AUS200"
}
# Словарь для Радара (Yahoo Finance)
YF_SYMBOLS = {
    "EUR/USD": "EURUSD=X", "USD/JPY": "USDJPY=X", "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "EUR/AUD": "EURAUD=X", "XAU/USD (Gold)": "GC=F",
    "BTC/USD (Bitcoin)": "BTC-USD", "SPX500": "^GSPC", "GER40 (DAX)": "^GDAXI",
    "JPN225": "^N225", "AUS200": "^AXJO"
}

TF_MAP = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h", "D1": "1day", "W1": "1week", "MN1": "1month", "MN6": "6month", "MN24": "24month"}
BASE_INTERVAL = {"M1": "1min", "M5": "5min", "M15": "5min", "M30": "5min", "H1": "1h", "H2": "1h", "H4": "1h", "H8": "1h", "D1": "1h", "W1": "1week", "MN1": "1month", "MN6": "1month", "MN24": "1month"}
RESAMPLE_RULE = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h", "D1": "1D", "W1": "W-MON", "MN6": "6MS", "MN24": "24MS"}
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]

# ==========================================
# 2. ФУНКЦИИ (Твой идеальный код)
# ==========================================
def server_offset_hours(choice):
    if choice == "UTC+2": return 2
    if choice == "UTC+3": return 3
    if choice == "UTC": return 0
    zone = ZoneInfo("Europe/Bucharest")
    return int(datetime.now(zone).utcoffset().total_seconds() // 3600)

def is_fx(symbol):
    if symbol.startswith("BTC"): return False
    return "/" in symbol

def fmt_price(price):
    if price >= 1000: return f"{price:.2f}"
    if price >= 10: return f"{price:.3f}"
    return f"{price:.5f}"

def fetch_raw(symbol, interval, outputsize=5000, tz="UTC"):
    params = {"symbol": symbol, "interval": interval, "apikey": API_KEY, "outputsize": outputsize, "order": "ASC"}
    if tz: params["timezone"] = tz
    response = requests.get("https://api.twelvedata.com/time_series", params=params, timeout=30)
    payload = response.json()
    if "values" not in payload: return pd.DataFrame(), payload.get("message") or str(payload)
    df = pd.DataFrame(payload["values"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=bool(tz))
    df = df.set_index("datetime").sort_index()
    for col in ("open", "high", "low", "close"): df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    good = (df["high"] >= df["low"]) & (df["close"] > 0)
    df = df.loc[good]
    df = df.groupby(level=0).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    return df, None

def forex_session(df_utc, offset, drop_weekend, drop_clearing):
    if df_utc.empty or not (drop_weekend or drop_clearing): return df_utc
    minutes = np.asarray(df_utc.index.hour * 60 + df_utc.index.minute)
    dow = np.asarray(df_utc.index.dayofweek)
    closed = np.zeros(len(df_utc), dtype=bool)
    if drop_weekend:
        close_min = ((24 - offset) % 24) * 60
        friday_late = (dow == 4) & (minutes >= close_min)
        sunday_early = (dow == 6) & (minutes < close_min)
        closed = (dow == 5) | friday_late | sunday_early
    if drop_clearing and offset != 0:
        break_min = ((23 - offset) % 24) * 60
        clearing = minutes >= break_min
        clearing = clearing & (minutes < break_min + 60)
        closed = np.asarray(closed) | np.asarray(clearing)
    keep = np.flatnonzero(np.asarray(closed) == False)
    return df_utc.iloc[keep]

def to_server_naive(df_utc, offset):
    if df_utc.empty: return df_utc
    server = timezone(timedelta(hours=offset))
    out = df_utc.copy()
    out.index = df_utc.index.tz_convert(server).tz_localize(None)
    return out

def resample_ohlc(df, rule):
    if df.empty: return df
    out = df.resample(rule, origin="start_day", label="left", closed="left")
    out = out.agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last")).dropna()
    good = (out["High"] >= out["Low"]) & (out["Close"] > 0)
    return out.loc[good]

@st.cache_data(ttl=60)
def load_chart(symbol, tf_name, offset, drop_weekend, drop_clearing):
    rebuild = is_fx(symbol) and tf_name not in ("W1", "MN1", "MN6", "MN24")
    if rebuild: base, zone = BASE_INTERVAL[tf_name], "UTC"
    else: base, zone = TF_MAP[tf_name], None
    raw, err = fetch_raw(symbol, base, tz=zone)
    if err or raw.empty:
        raw, err = fetch_raw(symbol, base, outputsize=400, tz=zone)
        if err or raw.empty: return pd.DataFrame(), err or "пустой ответ", 0
    dropped = 0
    if rebuild:
        before = len(raw)
        raw = forex_session(raw, offset, drop_weekend, drop_clearing)
        dropped = before - len(raw)
        raw = to_server_naive(raw, offset)
        raw = resample_ohlc(raw, RESAMPLE_RULE[tf_name])
    elif getattr(raw.index, "tz", None) is not None:
        raw = raw.copy()
        raw.index = raw.index.tz_localize(None)
    
    if not raw.empty and tf_name in ["MN6", "MN24"]:
        raw = resample_ohlc(raw, RESAMPLE_RULE[tf_name])
        
    return raw, None, dropped

def add_indicators(df):
    out = df.copy()
    prev = out["Close"].shift(1)
    tr = pd.concat([out["High"] - out["Low"], (out["High"] - prev).abs(), (out["Low"] - prev).abs()], axis=1).max(axis=1)
    out["ATR"] = tr.rolling(14).mean()
    high, low = out["High"], out["Low"]
    out["tenkan"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    out["kijun"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    out["raw_senkou_a"] = (out["tenkan"] + out["kijun"]) / 2
    out["raw_senkou_b"] = (high.rolling(52).max() + low.rolling(52).min()) / 2
    
    above_l, above_r = (high > high.shift(1)) & (high > high.shift(2)), (high > high.shift(-1)) & (high > high.shift(-2))
    below_l, below_r = (low < low.shift(1)) & (low < low.shift(2)), (low < low.shift(-1)) & (low < low.shift(-2))
    out["Minor_High"], out["Minor_Low"] = above_l & above_r, below_l & below_r
    out["Major_High"], out["Major_Low"] = True, True
    for i in range(1, 11):
        out["Major_High"] &= (high > high.shift(i)) & (high > high.shift(-i))
        out["Major_Low"] &= (low < low.shift(i)) & (low < low.shift(-i))
    return out

def marker_y(price, atr, direction, factor):
    span = atr.fillna(price.diff().abs().median() or 0)
    return price + direction * span * factor

def add_dots(fig, frame, price_col, direction, factor, size, color, name, kind):
    if frame.empty: return
    y = marker_y(frame[price_col], frame["ATR"], direction, factor)
    custom = np.column_stack([frame[price_col].to_numpy(), np.full(len(frame), kind)])
    tip = "Хай %{customdata[0]:.5f}<extra>" + name + "</extra>" if kind == "H" else "Лоу %{customdata[0]:.5f}<extra>" + name + "</extra>"
    fig.add_trace(go.Scatter(x=frame["x_idx"], y=y, mode="markers", marker=dict(size=size, color=color), name=name, customdata=custom, hovertemplate=tip))

def resolve_click(point, df_plot):
    x = point.get("x")
    if x is None: return None
    rows = df_plot.loc[df_plot["x_idx"] == x]
    if rows.empty: return None
    row = rows.iloc[0]
    curve = point.get("curveNumber", point.get("curve_number"))
    custom = point.get("customdata")
    kind = str(custom[1]) if isinstance(custom, (list, tuple)) and len(custom) >= 2 else None
    
    if kind == "H" or curve in (1, 3): return float(row["High"])
    if kind == "L" or curve in (2, 4): return float(row["Low"])
    if curve == 0:
        y = point.get("y")
        if y is None: return float(row["High"])
        return float(row["High"]) if abs(float(y) - row["High"]) <= abs(float(y) - row["Low"]) else float(row["Low"])
    return None

# ==========================================
# 🚀 ВКЛАДКИ САЙТА
# ==========================================
tab_radar, tab_terminal = st.tabs(["📡 Глобальный Радар", "📈 Терминал Архитектора"])

# ==========================================
# 📡 ВКЛАДКА 1: ГЛОБАЛЬНЫЙ РАДАР
# ==========================================
with tab_radar:
    st.markdown("#### Сканирование рынка (Безлимитный поток Yahoo Finance)")
    st.write("Выберите таймфреймы, на которых вы хотите найти сигнал в Окопе Киджун:")
    
    # 🎛 Горизонтальные радио-кнопки (без выпадающего меню!)
    radar_tfs = ["M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1", "MN6", "MN24"]
    radar_tf = st.radio("Рабочий Таймфрейм:", radar_tfs, index=6, horizontal=True)
    
    if st.button("🚀 ЗАПУСТИТЬ РАДАР", use_container_width=True):
        progress_text = "Гонцы сканируют рынки..."
        my_bar = st.progress(0, text=progress_text)
        radar_results = []
        
        # Определяем Старшего Брата
        RADAR_HTF_MAP = {"M15": "H4", "M30": "H4", "H1": "D1", "H2": "D1", "H4": "W1", "H8": "W1", "D1": "MN1", "W1": "MN1", "MN1": "MN1", "MN6": "MN24", "MN24": "MN24"}
        htf_radar = RADAR_HTF_MAP.get(radar_tf, "MN1")
        
        for i, (asset_name, _) in enumerate(ASSETS.items()):
            my_bar.progress((i + 1) / len(ASSETS), text=f"Анализирую {asset_name}...")
            yf_sym = YF_SYMBOLS[asset_name]
            
            try:
                per_ltf = "60d" if radar_tf in ["M15", "M30"] else "700d"
                per_htf = "700d" if htf_radar in ["H4", "D1"] else "20y"
                int_ltf = radar_tf.lower() if radar_tf in ["M15", "M30"] else ("1h" if "H" in radar_tf else "1d")
                int_htf = "1h" if htf_radar == "H4" else ("1d" if htf_radar == "D1" else ("1wk" if htf_radar == "W1" else "1mo"))
                
                df_ltf = yf.download(yf_sym, period=per_ltf, interval=int_ltf, progress=False)
                df_htf = yf.download(yf_sym, period=per_htf, interval=int_htf, progress=False)
                
                if df_ltf.empty or df_htf.empty: continue
                if isinstance(df_ltf.columns, pd.MultiIndex): df_ltf.columns = df_ltf.columns.get_level_values(0)
                if isinstance(df_htf.columns, pd.MultiIndex): df_htf.columns = df_htf.columns.get_level_values(0)
                df_ltf = df_ltf.rename(columns=lambda x: x.capitalize())
                df_htf = df_htf.rename(columns=lambda x: x.capitalize())
                
                if radar_tf in ["H2", "H4", "H8", "MN6", "MN24"]: df_ltf = resample_ohlc(df_ltf, RESAMPLE_RULE[radar_tf])
                if htf_radar in ["H2", "H4", "H8", "MN6", "MN24"]: df_htf = resample_ohlc(df_htf, RESAMPLE_RULE[htf_radar])
                
                df_ltf = add_indicators(df_ltf)
                df_htf = add_indicators(df_htf)
                
                h_c = df_htf.iloc[-2]
                is_bull = float(h_c["Close"]) > max(float(h_c["raw_senkou_a"]), float(h_c["raw_senkou_b"])) and float(h_c["tenkan"]) >= float(h_c["kijun"])
                is_bear = float(h_c["Close"]) < min(float(h_c["raw_senkou_a"]), float(h_c["raw_senkou_b"])) and float(h_c["tenkan"]) <= float(h_c["kijun"])
                trend = "🟢 Бычий" if is_bull else ("🔴 Медвежий" if is_bear else "➖ Флэт")
                
                l_c = df_ltf.iloc[-2]
                pr, kijun = float(l_c["Close"]), float(l_c["kijun"])
                near = abs(pr - kijun) <= (float(l_c["ATR"]) * 0.3)
                
                sig = "🟢 Покупка" if near and is_bull and float(l_c["tenkan"]) > kijun else ("🔴 Продажа" if near and is_bear and float(l_c["tenkan"]) < kijun else "⏳ Ждем")
                radar_results.append({"Актив": asset_name, "Старший Тренд": trend, "Сигнал (Окоп)": sig, "Цена": f"{pr:.5f}"})
            except: pass
            
        my_bar.empty()
        if radar_results:
            st.dataframe(pd.DataFrame(radar_results), use_container_width=True, hide_index=True)
        else:
            st.warning("Радар не смог просканировать рынки.")


# ==========================================
# 📈 ВКЛАДКА 2: ТЕРМИНАЛ ИШИМОКУ (TwelveData)
# ==========================================
with tab_terminal:
    st.markdown("#### ⚙️ Настройки Терминала")
    
    # Горизонтальные настройки (вместо боковой панели)
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1: asset_name_term = st.selectbox("Символ:", list(ASSETS.keys()), index=0, key="term_asset")
    with col_s2: tf_name = st.selectbox("Таймфрейм:", list(TF_MAP.keys()), index=4, key="term_tf")
    with col_s3: offset_choice = st.selectbox("Время сервера MT5", ["Авто (EET)", "UTC+2", "UTC+3", "UTC"], index=0)
    
    col_s4, col_s5, col_s6 = st.columns(3)
    with col_s4: count_weekend = st.checkbox("Считать субботу и ночь закрытия", value=False)
    with col_s5: drop_clearing = st.checkbox("Убирать час клиринга 23:00", value=False)
    with col_s6: 
        if st.button("🗑 Очистить точки A-B-C", use_container_width=True):
            st.session_state.abc_points = []
            st.rerun()

    offset = server_offset_hours(offset_choice)
    ticker = ASSETS[asset_name_term]

    # Табло точек
    st.markdown(f"**Выбрано точек:** {len(st.session_state.abc_points)}/3")
    cols_pts = st.columns(3)
    labels = ["A (Старт)", "B (Вершина/Дно)", "C (Откат)"]
    for i in range(3):
        with cols_pts[i]:
            if i < len(st.session_state.abc_points): st.success(f"{labels[i]}: {fmt_price(st.session_state.abc_points[i]['y'])}")
            else: st.info(f"Ожидаю {labels[i]}")

    st.markdown("---")

    df, err, dropped = load_chart(ticker, tf_name, offset, not count_weekend, drop_clearing)

    if err: st.error("Twelve Data: " + str(err))
    elif df.empty: st.warning("Нет данных после фильтра сессии.")
    else:
        df = add_indicators(df)
        df_plot = df.tail(250).copy()
        df_plot["x_idx"] = np.arange(len(df_plot))
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_plot["x_idx"], open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
            increasing_line_color="#2c3e50", increasing_fillcolor="white", increasing_line_width=1,
            decreasing_line_color="#2c3e50", decreasing_fillcolor="#2c3e50", decreasing_line_width=1, name="Свечи"
        ))

        minor_high = df_plot["Minor_High"] & df_plot["Major_High"].eq(False)
        minor_low = df_plot["Minor_Low"] & df_plot["Major_Low"].eq(False)
        add_dots(fig, df_plot.loc[minor_high], "High", 1, 0.20, 5, "#95a5a6", "Minor High", "H")
        add_dots(fig, df_plot.loc[minor_low], "Low", -1, 0.20, 5, "#95a5a6", "Minor Low", "L")
        
        major_high = df_plot.loc[df_plot["Major_High"]]
        major_low = df_plot.loc[df_plot["Major_Low"]]
        add_dots(fig, major_high, "High", 1, 0.50, 10, "#2c3e50", "Major High", "H")
        add_dots(fig, major_low, "Low", -1, 0.50, 10, "#2c3e50", "Major Low", "L")

        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["tenkan"], line=dict(color="#2980b9", width=1.5), name="Tenkan"))
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["kijun"], line=dict(color="#e74c3c", width=2), name="Kijun"))
        fig.add_trace(go.Scatter(x=df_plot["x_idx"] - 26, y=df_plot["Close"], line=dict(color="#1e8449", width=1.2), name="Chikou"))

        x_cloud = np.arange(len(df_plot)) + 26
        sa, sb = df_plot["raw_senkou_a"].to_numpy(dtype=float), df_plot["raw_senkou_b"].to_numpy(dtype=float)
        
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", fill="toself", fillcolor="rgba(128,128,128,0.3)", line=dict(width=0), name="Kumo (Облако)", legendgroup="cloud"))
        
        i, n, shown_up, shown_dn = 0, len(sa), False, False
        while i < n:
            if not (np.isfinite(sa[i]) and np.isfinite(sb[i])): i += 1; continue
            is_up = bool(sa[i] >= sb[i])
            j = i + 1
            while j < n and np.isfinite(sa[j]) and np.isfinite(sb[j]) and bool(sa[j] >= sb[j]) == is_up: j += 1
            end = j + 1 if j < n and np.isfinite(sa[j]) and np.isfinite(sb[j]) else j
            if end - i >= 2:
                xs, ys = np.concatenate([x_cloud[i:end], x_cloud[i:end][::-1]]), np.concatenate([sa[i:end], sb[i:end][::-1]])
                color = "rgba(46, 204, 113, 0.35)" if is_up else "rgba(231, 76, 60, 0.28)"
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=color, line=dict(width=0), showlegend=False, legendgroup="cloud", hoverinfo="skip"))
            i = j

        if len(st.session_state.abc_points) == 3:
            A, B, C = st.session_state.abc_points
            is_up = B["y"] > A["y"]
            if is_up: V, N, E, NT = B["y"] + (B["y"] - C["y"]), C["y"] + (B["y"] - A["y"]), B["y"] + (B["y"] - A["y"]), C["y"] + (C["y"] - A["y"])
            else: V, N, E, NT = B["y"] - (C["y"] - B["y"]), C["y"] - (A["y"] - B["y"]), B["y"] - (A["y"] - B["y"]), C["y"] - (A["y"] - C["y"])
            
            colors = {"V": "orange", "N": "green", "E": "red", "NT": "purple"}
            for name, val in {"V": V, "N": N, "E": E, "NT": NT}.items():
                fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text="Цель " + name + ": " + fmt_price(val), annotation_position="right")
            
            time_ab, time_ac = abs(B["x"] - A["x"]), abs(C["x"] - A["x"])
            fig.add_vline(x=C["x"] + time_ab, line_dash="dot", line_color="blue", annotation_text="Тайёсуу A-B (" + str(int(time_ab)) + ")")
            fig.add_vline(x=C["x"] + time_ac, line_dash="dot", line_color="teal", annotation_text="Тайёсуу A-C (" + str(int(time_ac)) + ")")
            for k in KIHON_SUU: fig.add_vline(x=C["x"] + k - 1, line_dash="dash", line_color="gray", annotation_text="Кихон (" + str(k) + ")", opacity=0.35)
                
            fig.add_trace(go.Scatter(x=[A["x"], B["x"], C["x"]], y=[A["y"], B["y"], C["y"]], mode="lines+markers", line=dict(color="gold", width=3), marker=dict(size=10), name="Волна A-B-C"))

        tick_step = max(1, len(df_plot) // 10)
        fig.update_layout(
            xaxis_rangeslider_visible=False, height=750, template="plotly_white", plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            margin=dict(l=20, r=80, t=40, b=80), yaxis=dict(side="right", tickformat=".5f", showgrid=True, gridcolor="#f0f0f0", fixedrange=False),
            xaxis=dict(tickmode="array", tickvals=df_plot["x_idx"].to_numpy()[::tick_step], ticktext=df_plot.index.strftime("%Y-%m-%d %H:%M")[::tick_step], showgrid=True, gridcolor="#f0f0f0", tickangle=45, fixedrange=False),
            hovermode="closest", clickmode="event+select", dragmode="pan", font=dict(color='#2c3e50'),
            legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
        )
        
        event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", config={"scrollZoom": False, "displayModeBar": True}, theme=None)
        if event and event.selection and event.selection.get("points"):
            clicked = event.selection["points"][0]
            price = resolve_click(clicked, df_plot)
            clicked_x = clicked.get("x")
            if price is not None and clicked_x is not None:
                if len(st.session_state.abc_points) < 3:
                    same = any(p["x"] == clicked_x for p in st.session_state.abc_points)
                    if not same:
                        st.session_state.abc_points.append({"x": clicked_x, "y": price})
                        st.rerun()
