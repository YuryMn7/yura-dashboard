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

st.set_page_config(page_title="Quantitative Analysis Terminal", layout="wide")

if "abc_points" not in st.session_state:
    st.session_state.abc_points = []

# ==========================================
# 1. КОНСТАНТЫ И СЛОВАРИ
# ==========================================
ASSET_ROUTER = {
    "EUR/USD": {"prov": "twelvedata", "sym": "EUR/USD", "yf": "EURUSD=X"},
    "USD/JPY": {"prov": "twelvedata", "sym": "USD/JPY", "yf": "USDJPY=X"},
    "GBP/USD": {"prov": "twelvedata", "sym": "GBP/USD", "yf": "GBPUSD=X"},
    "AUD/USD": {"prov": "twelvedata", "sym": "AUD/USD", "yf": "AUDUSD=X"},
    "NZD/USD": {"prov": "twelvedata", "sym": "NZD/USD", "yf": "NZDUSD=X"},
    "EUR/JPY": {"prov": "twelvedata", "sym": "EUR/JPY", "yf": "EURJPY=X"},
    "GBP/JPY": {"prov": "twelvedata", "sym": "GBP/JPY", "yf": "GBPJPY=X"},
    "EUR/AUD": {"prov": "twelvedata", "sym": "EUR/AUD", "yf": "EURAUD=X"},
    "XAU/USD (Gold)": {"prov": "twelvedata", "sym": "XAU/USD", "yf": "GC=F"},
    "BTC/USD (Bitcoin)": {"prov": "twelvedata", "sym": "BTC/USD", "yf": "BTC-USD"},
    "SPX500": {"prov": "yahoo", "sym": "SPX", "yf": "^GSPC"},
    "GER40 (DAX)": {"prov": "yahoo", "sym": "GDAXI", "yf": "^GDAXI"},
    "JPN225": {"prov": "yahoo", "sym": "N225", "yf": "^N225"},
    "AUS200": {"prov": "yahoo", "sym": "AUS200", "yf": "^AXJO"}
}

TF_MAP = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h", "D1": "1day", "W1": "1week", "MN1": "1month", "MN6": "6month", "MN24": "24month"}
BASE_INTERVAL = {"M1": "1min", "M5": "5min", "M15": "5min", "M30": "5min", "H1": "1h", "H2": "1h", "H4": "1h", "H8": "1h", "D1": "1h", "W1": "1week", "MN1": "1month", "MN6": "1month", "MN24": "1month"}
RESAMPLE_RULE = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h", "D1": "1D", "W1": "W-MON", "MN6": "6MS", "MN24": "24MS"}
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]

# ==========================================
# 2. ФУНКЦИИ ОЧИСТКИ И ДОБЫЧИ (Идеальные)
# ==========================================
def server_offset_hours(choice):
    if choice == "UTC+2": return 2
    if choice == "UTC+3": return 3
    if choice == "UTC": return 0
    zone = ZoneInfo("Europe/Bucharest")
    return int(datetime.now(zone).utcoffset().total_seconds() // 3600)

def is_fx(symbol):
    if "BTC" in symbol: return False
    return "/" in symbol

def fmt_price(price):
    if price >= 1000: return f"{price:.2f}"
    if price >= 10: return f"{price:.3f}"
    return f"{price:.5f}"

def fetch_raw(asset_key, base_int, force_provider=None, tz="UTC"):
    route = ASSET_ROUTER[asset_key]
    provider = force_provider if force_provider else route["prov"]
    
    if provider == "yahoo":
        ysym = route["yf"]
        y_int_map = {"1min":"1m", "5min":"5m", "15min":"15m", "30min":"30m", "1h":"1h", "1day":"1d", "1week":"1wk", "1month":"1mo"}
        y_int = y_int_map.get(base_int, "1d")
        per = "2y"
        if y_int == "1m": per = "5d"
        elif y_int in ["5m", "15m", "30m"]: per = "60d"
        elif y_int == "1h": per = "700d"
        elif y_int == "1d": per = "10y"
        elif y_int == "1wk": per = "15y"
        elif y_int == "1mo": per = "max"
        
        try:
            df = yf.download(ysym, period=per, interval=y_int, progress=False)
            if df.empty: return pd.DataFrame(), None
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.rename(columns=lambda x: x.capitalize())
            if getattr(df.index, "tz", None) is None: df.index = df.index.tz_localize("UTC")
            else: df.index = df.index.tz_convert("UTC")
            return df, None
        except: return pd.DataFrame(), None
    else:
        sym = route["sym"]
        params = {"symbol": sym, "interval": base_int, "apikey": API_KEY, "outputsize": 4000, "order": "ASC"}
        if tz: params["timezone"] = tz
        try:
            res = requests.get("https://api.twelvedata.com/time_series", params=params, timeout=10).json()
            if 'values' not in res: return pd.DataFrame(), None
            df = pd.DataFrame(res['values'])
            df['datetime'] = pd.to_datetime(df['datetime'], utc=bool(tz))
            df = df.set_index('datetime').sort_index()
            for col in ['open', 'high', 'low', 'close']: df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["open", "high", "low", "close"])
            good = (df["high"] >= df["low"]) & (df["close"] > 0)
            df = df.loc[good]
            df = df.groupby(level=0).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
            df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
            return df, None
        except: return pd.DataFrame(), None

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
def load_chart(asset_key, tf_name, offset, drop_weekend, drop_clearing, force_provider=None):
    is_fx_flag = is_fx(ASSET_ROUTER[asset_key]["sym"])
    rebuild = is_fx_flag and tf_name not in ("W1", "MN1", "MN6", "MN24")
    base = BASE_INTERVAL[tf_name] if rebuild else TF_MAP.get(tf_name, "1h")
    zone = "UTC" if rebuild else None
    
    raw, err = fetch_raw(asset_key, base, force_provider, tz=zone)
    if raw.empty: return pd.DataFrame()
    
    if rebuild:
        raw = forex_session(raw, offset, drop_weekend, drop_clearing, is_fx_flag)
        raw = to_server_naive(raw, offset)
        raw = resample_ohlc(raw, RESAMPLE_RULE[tf_name])
    elif getattr(raw.index, "tz", None) is not None:
        raw.index = raw.index.tz_localize(None)
        
    if not raw.empty and tf_name in ["MN6", "MN24"]:
        raw = resample_ohlc(raw, RESAMPLE_RULE[tf_name])
        
    return raw

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
    out["senkou_a"] = out["raw_senkou_a"].shift(26)
    out["senkou_b"] = out["raw_senkou_b"].shift(26)
    out["chikou"] = out["Close"].shift(-26)
    
    above_l, above_r = (high > high.shift(1)) & (high > high.shift(2)), (high > high.shift(-1)) & (high > high.shift(-2))
    below_l, below_r = (low < low.shift(1)) & (low < low.shift(2)), (low < low.shift(-1)) & (low < low.shift(-2))
    out["Minor_High"], out["Minor_Low"] = above_l & above_r, below_l & below_r
    out["Major_High"], out["Major_Low"] = True, True
    for i in range(1, 11):
        out["Major_High"] &= (high > high.shift(i)) & (high > high.shift(-i))
        out["Major_Low"] &= (low < low.shift(i)) & (low < low.shift(-i))
    return out

# ==========================================
# 3. ГЛОБАЛЬНОЕ БОКОВОЕ МЕНЮ
# ==========================================
with st.sidebar:
    st.markdown("### Настройки Платформы")
    offset_choice = st.selectbox("Часовой пояс сервера (MT5):", ["Авто (EET)", "UTC+2", "UTC+3", "UTC"], index=0)
    count_weekend = st.checkbox("Отображать выходные дни", value=False)
    drop_clearing = st.checkbox("Удалять клиринг (23:00)", value=True)
    offset = server_offset_hours(offset_choice)

# ==========================================
# 4. ВКЛАДКИ
# ==========================================
tab_radar, tab_terminal = st.tabs(["📡 Market Scanner", "📈 Analytical Terminal"])

# ----------------- РАДАР -----------------
with tab_radar:
    st.markdown("#### Массовое сканирование рынка")
    # Убрали MN6 и MN24 из радара
    radar_tfs = ["M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1"]
    radar_tf = st.radio("Рабочий Таймфрейм:", radar_tfs, index=6, horizontal=True)
    
    if st.button("🚀 ЗАПУСТИТЬ СКАНИРОВАНИЕ", use_container_width=True):
        my_bar = st.progress(0, text="Сканирование рынков...")
        radar_results = []
        RADAR_HTF_MAP = {"M15": "H4", "M30": "H4", "H1": "D1", "H2": "D1", "H4": "W1", "H8": "W1", "D1": "MN1", "W1": "MN1", "MN1": "MN1"}
        htf_radar = RADAR_HTF_MAP.get(radar_tf, "MN1")
        
        for i, asset_name in enumerate(ASSET_ROUTER.keys()):
            my_bar.progress((i + 1) / len(ASSET_ROUTER), text=f"Анализ {asset_name}...")
            try:
                # Радар жестко использует Yahoo для избежания лимитов API
                df_ltf = load_chart(asset_name, radar_tf, offset, not count_weekend, drop_clearing, force_provider="yahoo")
                df_htf = load_chart(asset_name, htf_radar, offset, not count_weekend, drop_clearing, force_provider="yahoo")
                
                if df_ltf.empty or df_htf.empty or len(df_ltf) < 55 or len(df_htf) < 55: continue
                
                df_ltf = add_indicators(df_ltf)
                df_htf = add_indicators(df_htf)
                
                h_c = df_htf.iloc[-2]
                # 🛠 ИСПРАВЛЕНИЕ: Берем текущее облако (senkou_a/b), а не будущее (raw)
                kumo_top = max(float(h_c["senkou_a"]), float(h_c["senkou_b"]))
                kumo_bot = min(float(h_c["senkou_a"]), float(h_c["senkou_b"]))
                
                is_bull = float(h_c["Close"]) > kumo_top and float(h_c["tenkan"]) >= float(h_c["kijun"])
                is_bear = float(h_c["Close"]) < kumo_bot and float(h_c["tenkan"]) <= float(h_c["kijun"])
                trend = "🟢 Бычий" if is_bull else ("🔴 Медвежий" if is_bear else "➖ Флэт")
                
                l_c = df_ltf.iloc[-2]
                pr, kijun = float(l_c["Close"]), float(l_c["kijun"])
                near = abs(pr - kijun) <= (float(l_c["ATR"]) * 0.3)
                sig = "🟢 Покупка" if near and is_bull and float(l_c["tenkan"]) > kijun else ("🔴 Продажа" if near and is_bear and float(l_c["tenkan"]) < kijun else "⏳ Ждем")
                
                radar_results.append({"Актив": asset_name, "Старший Тренд": trend, "Сигнал (Окоп)": sig, "Цена": f"{pr:.5f}"})
            except: pass
            
        my_bar.empty()
        if radar_results: st.dataframe(pd.DataFrame(radar_results), use_container_width=True, hide_index=True)
        else: st.warning("🏁 Сканирование завершено. Сигналов не найдено.")

# ----------------- ТЕРМИНАЛ -----------------
with tab_terminal:
    col_t1, col_t2, col_t3 = st.columns([2, 2, 1])
    with col_t1: asset_term = st.selectbox("Актив:", list(ASSET_ROUTER.keys()), index=0)
    with col_t2: tf_term = st.selectbox("Таймфрейм:", list(TF_MAP.keys()), index=4)
    with col_t3: 
        st.write("")
        st.write("")
        if st.button("🗑 Сброс точек", use_container_width=True):
            st.session_state.abc_points = []
            st.rerun()

    cols_pts = st.columns(3)
    labels = ["A (Старт)", "B (Вершина/Дно)", "C (Откат)"]
    for i in range(3):
        with cols_pts[i]:
            if i < len(st.session_state.abc_points): st.success(f"{labels[i]}: {fmt_price(st.session_state.abc_points[i]['y'])}")
            else: st.info(f"Ожидаю {labels[i]}")

    df_raw = load_chart(asset_term, tf_term, offset, not count_weekend, drop_clearing)

    if df_raw.empty:
        st.warning("Данные недоступны.")
    else:
        df = add_indicators(df_raw)
        df_plot = df.tail(250).copy()
        df_plot["x_idx"] = np.arange(len(df_plot))
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_plot["x_idx"], open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
            increasing_line_color="#2c3e50", increasing_fillcolor="white", increasing_line_width=1,
            decreasing_line_color="#2c3e50", decreasing_fillcolor="#2c3e50", decreasing_line_width=1, name="Свечи"
        ))

        def add_dots(frame, col, sign, factor, size, color, name, kind):
            if frame.empty: return
            y = frame[col] + sign * frame["ATR"].fillna(0) * factor
            custom = np.column_stack([frame[col].to_numpy(), np.full(len(frame), kind)])
            tip = "Хай %{customdata[0]:.5f}<extra></extra>" if kind == "H" else "Лоу %{customdata[0]:.5f}<extra></extra>"
            fig.add_trace(go.Scatter(x=frame["x_idx"], y=y, mode="markers", marker=dict(size=size, color=color), name=name, customdata=custom, hovertemplate=tip))

        add_dots(df_plot.loc[df_plot["Minor_High"] & ~df_plot["Major_High"]], "High", 1, 0.20, 5, "#95a5a6", "Младший Максимум", "H")
        add_dots(df_plot.loc[df_plot["Minor_Low"] & ~df_plot["Major_Low"]], "Low", -1, 0.20, 5, "#95a5a6", "Младший Минимум", "L")
        add_dots(df_plot.loc[df_plot["Major_High"]], "High", 1, 0.50, 10, "#2c3e50", "Старший Максимум", "H")
        add_dots(df_plot.loc[df_plot["Major_Low"]], "Low", -1, 0.50, 10, "#2c3e50", "Старший Минимум", "L")

        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["tenkan"], line=dict(color="#2980b9", width=1.5), name="Tenkan-sen"))
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["kijun"], line=dict(color="#e74c3c", width=2), name="Kijun-sen"))
        fig.add_trace(go.Scatter(x=df_plot["x_idx"] - 26, y=df_plot["Close"], line=dict(color="#1e8449", width=1.2, dash='dashdot'), name="Chikou Span"))

        x_cloud = np.arange(len(df_plot)) + 26
        sa, sb = df_plot["raw_senkou_a"].to_numpy(dtype=float), df_plot["raw_senkou_b"].to_numpy(dtype=float)
        
        # Облако (Скрыто в легенде, единая группа)
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", fill="toself", fillcolor="rgba(128,128,128,0.3)", line=dict(width=0), name="Kumo Cloud", legendgroup="cloud"))
        
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
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=color, line=dict(width=0), showlegend=False, legendgroup="cloud", hoverinfo="skip"))
            i = j

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
            for k in KIHON_SUU: fig.add_vline(x=C["x"] + k - 1, line_dash="dash", line_color="gray", annotation_text=f"Кихон ({k})", opacity=0.35)
                
            fig.add_trace(go.Scatter(x=[A["x"], B["x"], C["x"]], y=[A["y"], B["y"], C["y"]], mode="lines+markers", line=dict(color="#f39c12", width=2), marker=dict(size=8), name="Волна A-B-C"))

        tick_step = max(1, len(df_plot) // 10)
        fig.update_layout(
            xaxis_rangeslider_visible=False, height=750, template="plotly_white", plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            margin=dict(l=20, r=80, t=40, b=60), # 🛠 Подняли легенду выше (b=60)
            yaxis=dict(side="right", tickformat=".5f", showgrid=True, gridcolor="#f0f0f0", fixedrange=False),
            xaxis=dict(tickmode="array", tickvals=df_plot["x_idx"].to_numpy()[::tick_step], ticktext=df_plot.index.strftime("%Y-%m-%d %H:%M")[::tick_step], showgrid=True, gridcolor="#f0f0f0", tickangle=45, fixedrange=False),
            hovermode="closest", clickmode="event+select", dragmode="pan", font=dict(color='#2c3e50'),
            legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5) # 🛠 Легенда аккуратно под датами
        )
        
        # 🛠 ОЧИСТКА ВМЕШАТЕЛЬСТВА В ТЕМУ (theme=None)
        event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", config={"scrollZoom": False, "displayModeBar": True}, theme=None)
        
        if event and event.selection and event.selection.get("points"):
            clicked = event.selection["points"][0]
            x_val = clicked.get("x")
            if x_val is not None:
                rows = df_plot.loc[df_plot["x_idx"] == x_val]
                if not rows.empty:
                    row = rows.iloc[0]
                    # Идеальный клик
                    y_val = clicked.get("y")
                    price = float(row["High"]) if y_val is None or abs(float(y_val)-row["High"]) <= abs(float(y_val)-row["Low"]) else float(row["Low"])
                    if len(st.session_state.abc_points) < 3 and not any(p["x"] == x_val for p in st.session_state.abc_points):
                        st.session_state.abc_points.append({"x": x_val, "y": price})
                        st.rerun()
        gc.collect()
