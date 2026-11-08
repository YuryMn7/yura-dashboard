import gc
import re
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# set_page_config должен быть первым вызовом Streamlit
st.set_page_config(page_title="Quantitative Analysis Terminal", layout="wide")

API_KEY = st.secrets["TWELVEDATA_KEY"]

# Совместимость: в Streamlit >= 1.50 use_container_width заменён на width="stretch"
_ST_VER = tuple(int(x) for x in re.findall(r"\d+", st.__version__)[:2])
WIDE = {"width": "stretch"} if _ST_VER >= (1, 50) else {"use_container_width": True}

st.session_state.setdefault("abc_points", [])
st.session_state.setdefault("chart_ver", 0)


def reset_points():
    st.session_state.abc_points = []
    st.session_state.chart_ver += 1  # новый key -> выделение на графике тоже сбрасывается


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
    "AUS200": {"prov": "yahoo", "sym": "AUS200", "yf": "^AXJO"},
}

# Интервалы TwelveData
TF_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h",
    "D1": "1day", "W1": "1week", "MN1": "1month", "MN6": "6month", "MN24": "24month",
}

# Интервалы Yahoo: (interval, period)
YF_MAP = {
    "M1": ("1m", "5d"),
    "M5": ("5m", "60d"), "M15": ("15m", "60d"), "M30": ("30m", "60d"),
    "H1": ("1h", "700d"), "H2": ("1h", "700d"), "H4": ("1h", "700d"), "H8": ("1h", "700d"),
    "D1": ("1d", "10y"), "W1": ("1wk", "15y"),
    "MN1": ("1mo", "max"), "MN6": ("1mo", "max"), "MN24": ("1mo", "max"),
}

# Таймфреймы, которые собираются ресемплингом из базового
BASE_TF = {"H2": "H1", "H4": "H1", "H8": "H1", "MN6": "MN1", "MN24": "MN1"}
RESAMPLE_RULE = {"H2": "2h", "H4": "4h", "H8": "8h", "MN6": "6MS", "MN24": "24MS"}

RADAR_HTF_MAP = {
    "M15": "H4", "M30": "H4", "H1": "D1", "H2": "D1", "H4": "W1", "H8": "W1",
    "D1": "MN1", "W1": "MN1", "MN1": "MN1", "MN6": "MN24", "MN24": "MN24",
}

# Минимум баров: Senkou B = 52 + сдвиг 26 -> первое валидное значение на индексе 77.
# LTF смотрим на iloc[-28] -> нужно >= 105; HTF на iloc[-2] -> нужно >= 79.
MIN_LTF_BARS = 110
MIN_HTF_BARS = 80

KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]


# ==========================================
# 2. ЯДРО ОБРАБОТКИ ДАННЫХ
# ==========================================
def safe_err(e):
    """Текст ошибки без ключа API."""
    return f"{type(e).__name__}: {e}".replace(API_KEY, "***")


def align_start(df, rule):
    """6- и 24-месячные свечи начинаем с календарной границы (Янв/Июл; чётный год)."""
    if df.empty:
        return df
    if rule == "6MS":
        ok = np.asarray(df.index.month.isin([1, 7]))
    elif rule == "24MS":
        ok = np.asarray(df.index.month == 1) & np.asarray(df.index.year % 2 == 0)
    else:
        return df
    pos = np.flatnonzero(ok)
    return df.iloc[pos[0]:] if len(pos) else df.iloc[0:0]


def resample_ohlc(df, rule):
    if df.empty:
        return df
    df = align_start(df, rule)
    if df.empty:
        return df
    kw = {} if "MS" in rule else {"origin": "start_day"}
    out = df.resample(rule, label="left", closed="left", **kw).agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    ).dropna()
    return out.loc[(out["High"] >= out["Low"]) & (out["Close"] > 0)]


def drop_weekend_ny(df_utc):
    """Межбанк закрыт: пятница 17:00 NY -> воскресенье 17:00 NY.
    Убираем субботу и закрытые часы; воскресный вечер (после 17:00 NY) ОСТАВЛЯЕМ.
    Считаем по времени Нью-Йорка, поэтому летнее время (21:00/22:00 UTC) учтено автоматически.
    Индекс бара = время открытия бара."""
    if df_utc.empty:
        return df_utc
    ny = df_utc.index.tz_convert("America/New_York")
    dow = np.asarray(ny.dayofweek)
    hour = np.asarray(ny.hour)
    closed = (dow == 5) | ((dow == 4) & (hour >= 17)) | ((dow == 6) & (hour < 17))
    return df_utc.iloc[np.flatnonzero(~closed)]


def glue_sunday(df):
    """D1: воскресная свеча приклеивается к понедельнику (как в MT5)."""
    if df.empty:
        return df
    df = df.sort_index()
    shift = pd.to_timedelta((np.asarray(df.index.dayofweek) == 6).astype(int), unit="D")
    out = df.copy()
    out.index = df.index + shift
    return out.groupby(level=0).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})


@st.cache_data(ttl=300, show_spinner=False)
def fetch_yahoo(sym, interval):
    """Возвращает (df_utc, error). Данные БЕЗ ресемплинга (базовый ТФ)."""
    yf_int, per = YF_MAP[interval]
    try:
        df = yf.download(sym, period=per, interval=yf_int, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame(), f"Yahoo: нет данных для {sym} ({yf_int})"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=lambda x: str(x).capitalize())
        df = df[["Open", "High", "Low", "Close"]].dropna()
        idx = df.index
        df.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
        df = df[~df.index.duplicated(keep="last")].sort_index()
        return df, None
    except Exception as e:
        return pd.DataFrame(), safe_err(e)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_smart_data(asset_key, interval):
    """Возвращает (df_utc, error). Данные БЕЗ ресемплинга (базовый ТФ)."""
    route = ASSET_ROUTER[asset_key]
    if route["prov"] == "yahoo":
        return fetch_yahoo(route["yf"], interval)

    try:
        base_int = TF_MAP[BASE_TF.get(interval, interval)]
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={"symbol": route["sym"], "interval": base_int, "apikey": API_KEY, "outputsize": 5000, "timezone": "UTC"},
            timeout=10,
        )
        res = r.json()
        if "values" not in res:
            return pd.DataFrame(), f"TwelveData: {res.get('message', 'нет данных')}"

        df = pd.DataFrame(res["values"])
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        df = df.set_index("datetime").sort_index()
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
        df = df[["Open", "High", "Low", "Close"]].dropna()
        df = df[~df.index.duplicated(keep="last")]
        return df, None
    except Exception as e:
        return pd.DataFrame(), safe_err(e)


def add_indicators(df):
    out = df.copy()
    prev = out["Close"].shift(1)
    out["ATR"] = pd.concat(
        [out["High"] - out["Low"], (out["High"] - prev).abs(), (out["Low"] - prev).abs()], axis=1
    ).max(axis=1).rolling(14).mean()
    high, low = out["High"], out["Low"]

    out["tenkan"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    out["kijun"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    out["raw_senkou_a"] = (out["tenkan"] + out["kijun"]) / 2
    out["raw_senkou_b"] = (high.rolling(52).max() + low.rolling(52).min()) / 2
    out["senkou_a"] = out["raw_senkou_a"].shift(26)
    out["senkou_b"] = out["raw_senkou_b"].shift(26)
    out["chikou"] = out["Close"].shift(-26)

    out["Minor_High"] = (high > high.shift(1)) & (high > high.shift(2)) & (high > high.shift(-1)) & (high > high.shift(-2))
    out["Minor_Low"] = (low < low.shift(1)) & (low < low.shift(2)) & (low < low.shift(-1)) & (low < low.shift(-2))
    out["Major_High"], out["Major_Low"] = True, True
    for i in range(1, 11):
        out["Major_High"] &= (high > high.shift(i)) & (high > high.shift(-i))
        out["Major_Low"] &= (low < low.shift(i)) & (low < low.shift(-i))
    return out


def fmt_price(price):
    if price >= 1000:
        return f"{price:.2f}"
    if price >= 10:
        return f"{price:.3f}"
    return f"{price:.5f}"


def tick_fmt(price):
    if price >= 1000:
        return ".2f"
    if price >= 10:
        return ".3f"
    return ".5f"


# ==========================================
# 3. НАВИГАЦИЯ И ИНТЕРФЕЙС
# ==========================================
with st.sidebar:
    st.markdown("### Navigation")
    app_mode = st.radio("Select Module:", ["Market Scanner (Radar)", "Analytical Terminal"])

# ==========================================
# Вкладка 1: РАДАР
# ==========================================
if app_mode == "Market Scanner (Radar)":
    st.markdown("<h2 style='color: #2c3e50;'>Global Market Scanner</h2>", unsafe_allow_html=True)
    radar_tf = st.selectbox(
        "Select Timeframe:",
        ["M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1", "MN6", "MN24"],
        index=6,
    )

    def fetch_radar(route, tf):
        """Yahoo (UTC) + ресемплинг для H2/H4/H8/MN6/MN24."""
        df, err = fetch_yahoo(route["yf"], tf)
        if err or df.empty:
            return df, err or "нет данных"
        if tf in RESAMPLE_RULE:
            df = resample_ohlc(df, RESAMPLE_RULE[tf])
            if df.empty:
                return df, "нет данных после ресемплинга"
        return df, None

    if st.button("Execute Market Scan", **WIDE):
        my_bar = st.progress(0, text="Scanning market data...")
        radar_results, skipped = [], []
        htf_radar = RADAR_HTF_MAP.get(radar_tf, "MN1")

        for i, (asset_name, route) in enumerate(ASSET_ROUTER.items()):
            my_bar.progress((i + 1) / len(ASSET_ROUTER), text=f"Processing {asset_name}...")
            try:
                df_ltf, err_l = fetch_radar(route, radar_tf)
                df_htf, err_h = fetch_radar(route, htf_radar)
                if err_l or err_h:
                    skipped.append((asset_name, err_l or err_h))
                    continue
                if len(df_ltf) < MIN_LTF_BARS or len(df_htf) < MIN_HTF_BARS:
                    skipped.append((
                        asset_name,
                        f"мало баров (LTF {len(df_ltf)}/{MIN_LTF_BARS}, HTF {len(df_htf)}/{MIN_HTF_BARS})",
                    ))
                    continue

                df_ltf = add_indicators(df_ltf)
                df_htf = add_indicators(df_htf)

                h_c = df_htf.iloc[-2]
                l_c = df_ltf.iloc[-2]
                p_b = df_ltf.iloc[-28]  # свеча для проверки Чикоу (26 назад + сдвиг 2)

                h_v = h_c[["Close", "tenkan", "kijun", "senkou_a", "senkou_b"]].astype(float)
                l_v = l_c[["Close", "tenkan", "kijun", "senkou_a", "senkou_b", "ATR"]].astype(float)
                p_v = p_b[["High", "Low", "senkou_a", "senkou_b"]].astype(float)
                if h_v.isna().any() or l_v.isna().any() or p_v.isna().any():
                    skipped.append((asset_name, "индикаторы не готовы (NaN)"))
                    continue

                # --- СТАРШИЙ ТРЕНД ---
                h_kumo_top = max(h_v["senkou_a"], h_v["senkou_b"])
                h_kumo_bot = min(h_v["senkou_a"], h_v["senkou_b"])
                htf_bullish = h_v["Close"] > h_kumo_top and h_v["tenkan"] >= h_v["kijun"]
                htf_bearish = h_v["Close"] < h_kumo_bot and h_v["tenkan"] <= h_v["kijun"]
                trend_txt = "🟢 UP" if htf_bullish else ("🔴 DOWN" if htf_bearish else "➖ FLAT")

                # --- ЛОКАЛЬНАЯ ЗАСАДА ---
                pr, kijun = l_v["Close"], l_v["kijun"]
                l_kumo_top = max(l_v["senkou_a"], l_v["senkou_b"])
                l_kumo_bot = min(l_v["senkou_a"], l_v["senkou_b"])
                p_kumo_top = max(p_v["senkou_a"], p_v["senkou_b"])
                p_kumo_bot = min(p_v["senkou_a"], p_v["senkou_b"])

                chikou_buy = pr > p_v["High"] and pr > p_kumo_top
                chikou_sell = pr < p_v["Low"] and pr < p_kumo_bot

                bullish = l_v["tenkan"] > kijun and pr > l_kumo_top and chikou_buy
                bearish = l_v["tenkan"] < kijun and pr < l_kumo_bot and chikou_sell
                near_kijun = abs(pr - kijun) <= l_v["ATR"] * 0.3

                # --- СИГНАЛ ---
                sig = None
                if near_kijun:
                    if bullish:
                        sig = "🦅 STRONG BUY (HTF Confirmed)" if htf_bullish else "🟢 Local BUY"
                    elif bearish:
                        sig = "🦅 STRONG SELL (HTF Confirmed)" if htf_bearish else "🔴 Local SELL"

                if sig:
                    radar_results.append({
                        "Asset": asset_name,
                        "Signal": sig,
                        "HTF Trend": trend_txt,
                        "Price": fmt_price(pr),
                        "Kijun": fmt_price(kijun),
                    })
            except Exception as e:
                skipped.append((asset_name, safe_err(e)))

        my_bar.empty()
        if radar_results:
            st.dataframe(pd.DataFrame(radar_results), hide_index=True, **WIDE)
        else:
            st.info("Scan completed. No valid entry setups found near Kijun-sen.")

        if skipped:
            with st.expander(f"Skipped assets ({len(skipped)})"):
                st.dataframe(pd.DataFrame(skipped, columns=["Asset", "Reason"]), hide_index=True, **WIDE)

# ==========================================
# Вкладка 2: ТЕРМИНАЛ
# ==========================================
elif app_mode == "Analytical Terminal":

    SERVER_CHOICES = ["Auto (EET)", "NY close (UTC+2/+3)", "UTC+2", "UTC+3", "UTC"]

    def to_server_time(df_utc, choice):
        """UTC -> серверное время (наивный индекс)."""
        out = df_utc.copy()
        if choice == "NY close (UTC+2/+3)":
            # сервер = время Нью-Йорка + 7 ч (переход на летнее время по правилам США):
            # пт 17:00 NY = пт 24:00 сервера, вс 17:00 NY = пн 00:00 сервера
            out.index = out.index.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
        else:
            tz = {
                "Auto (EET)": "Europe/Bucharest",  # летнее время по правилам ЕС
                "UTC+2": timezone(timedelta(hours=2)),
                "UTC+3": timezone(timedelta(hours=3)),
                "UTC": timezone.utc,
            }[choice]
            out.index = out.index.tz_convert(tz).tz_localize(None)
        return out

    def drop_clearing_hour(df_srv, choice):
        """Убираем час 23:00 серверного времени (клиринг). Для UTC не применяется."""
        if df_srv.empty or choice == "UTC":
            return df_srv
        return df_srv[np.asarray(df_srv.index.hour) != 23]

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Terminal Settings")
        asset_name = st.selectbox("Symbol:", list(ASSET_ROUTER.keys()), index=0)
        tf_name = st.selectbox("Timeframe:", list(TF_MAP.keys()), index=4)
        offset_choice = st.selectbox("Server Time (MT5):", SERVER_CHOICES, index=0)
        count_weekend = st.checkbox(
            "Include Saturday & closing night (raw)", value=False,
            help="Выкл: суббота и закрытые часы (пт 17:00 NY — вс 17:00 NY) убраны, воскресный вечер остаётся. "
                 "Вкл: сырые данные провайдера без какой-либо фильтрации.",
        )
        drop_clearing = st.checkbox("Drop 23:00 Clearing", value=True, disabled=count_weekend)

        # смена символа/ТФ/настроек времени -> старые точки теряют смысл
        ctx = (asset_name, tf_name, offset_choice, count_weekend, drop_clearing)
        if st.session_state.get("ctx") != ctx:
            if "ctx" in st.session_state:
                reset_points()
            st.session_state.ctx = ctx

        st.markdown("---")
        st.markdown("### Wave Points (A-B-C)")
        labels = ["A (Start)", "B (Peak/Trough)", "C (Retracement)"]
        for i in range(3):
            if i < len(st.session_state.abc_points):
                p = st.session_state.abc_points[i]
                st.success(f"{labels[i]}: {fmt_price(p['y'])}  ({p['t']:%Y-%m-%d %H:%M})")
            else:
                st.info(f"Awaiting {labels[i]}...")
        if st.button("Clear Points", **WIDE):
            reset_points()
            st.rerun()

    df_raw, fetch_err = fetch_smart_data(asset_name, tf_name)
    sym = ASSET_ROUTER[asset_name]["sym"]
    is_fx_flag = ("/" in sym) and ("BTC" not in sym)

    if not df_raw.empty:
        filter_on = is_fx_flag and not count_weekend  # raw-режим: никакой фильтрации
        if tf_name == "D1":
            # D1: без сдвига времени; суббота — мусор, воскресенье приклеивается к понедельнику
            df_raw = df_raw.copy()
            df_raw.index = df_raw.index.tz_localize(None)
            if filter_on:
                df_raw = df_raw[np.asarray(df_raw.index.dayofweek) != 5]
                df_raw = glue_sunday(df_raw)
        elif tf_name in ("W1", "MN1", "MN6", "MN24"):
            df_raw = df_raw.copy()
            df_raw.index = df_raw.index.tz_localize(None)
            if tf_name in RESAMPLE_RULE:
                df_raw = resample_ohlc(df_raw, RESAMPLE_RULE[tf_name])
        else:
            # внутридневные: выходные (по NY) -> серверное время -> клиринг -> ресемплинг (H2/H4/H8)
            if filter_on:
                df_raw = drop_weekend_ny(df_raw)
            if not df_raw.empty:
                df_raw = to_server_time(df_raw, offset_choice)
                if filter_on and drop_clearing:
                    df_raw = drop_clearing_hour(df_raw, offset_choice)
                if tf_name in RESAMPLE_RULE:
                    df_raw = resample_ohlc(df_raw, RESAMPLE_RULE[tf_name])
        if not df_raw.empty:
            df_raw = df_raw[~df_raw.index.duplicated(keep="last")].sort_index()

    if df_raw.empty:
        st.warning("Market data is currently unavailable.")
        if fetch_err:
            st.caption(f"Причина: {fetch_err}")
    else:
        df = add_indicators(df_raw)
        df_plot = df.tail(250).copy()
        df_plot["x_idx"] = np.arange(len(df_plot))

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_plot["x_idx"], open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
            increasing_line_color="#2c3e50", increasing_fillcolor="white", increasing_line_width=1,
            decreasing_line_color="#2c3e50", decreasing_fillcolor="#2c3e50", decreasing_line_width=1, name="Price",
        ))  # trace 0

        last_close = float(df_plot["Close"].iloc[-1])
        pfmt = tick_fmt(last_close)
        time_txt = df_plot.index.strftime("%Y-%m-%d %H:%M").to_numpy()

        def marker_trace(mask, kind, price_col, offset_mult, size, color, name):
            """Маркер стоит выше/ниже свечи, но подсказка показывает именно High/Low свечи."""
            sub = df_plot.loc[mask]
            sign = 1 if kind == "High" else -1
            return go.Scatter(
                x=sub["x_idx"], y=sub[price_col] + sign * sub["ATR"] * offset_mult,
                mode="markers", marker=dict(size=size, color=color), name=name,
                customdata=sub[price_col].to_numpy(dtype=float), text=time_txt[np.flatnonzero(mask.to_numpy())],
                hovertemplate=f"{name}<br>{kind}: %{{customdata:{pfmt}}}<br>%{{text}}<extra></extra>",
            )

        minor_high = df_plot["Minor_High"] & ~df_plot["Major_High"]
        minor_low = df_plot["Minor_Low"] & ~df_plot["Major_Low"]
        major_high = df_plot["Major_High"]
        major_low = df_plot["Major_Low"]
        fig.add_trace(marker_trace(minor_high, "High", "High", 0.2, 5, "#95a5a6", "Minor High"))   # 1
        fig.add_trace(marker_trace(minor_low, "Low", "Low", 0.2, 5, "#95a5a6", "Minor Low"))       # 2
        fig.add_trace(marker_trace(major_high, "High", "High", 0.5, 10, "#2c3e50", "Major High"))  # 3
        fig.add_trace(marker_trace(major_low, "Low", "Low", 0.5, 10, "#2c3e50", "Major Low"))      # 4

        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["tenkan"], line=dict(color="#2980b9", width=1.5), name="Tenkan-sen"))  # 5
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["kijun"], line=dict(color="#e74c3c", width=2), name="Kijun-sen"))  # 6
        fig.add_trace(go.Scatter(x=df_plot["x_idx"] - 26, y=df_plot["Close"], line=dict(color="#1e8449", width=1.2, dash="dashdot"), name="Chikou Span"))  # 7

        x_cloud = np.arange(len(df_plot)) + 26
        sa, sb = df_plot["raw_senkou_a"].to_numpy(dtype=float), df_plot["raw_senkou_b"].to_numpy(dtype=float)

        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", fill="toself", fillcolor="rgba(128,128,128,0.3)", line=dict(width=0), name="Kumo Cloud", legendgroup="cloud"))

        i, n = 0, len(sa)
        while i < n:
            if not (np.isfinite(sa[i]) and np.isfinite(sb[i])):
                i += 1
                continue
            is_up = bool(sa[i] >= sb[i])
            j = i + 1
            while j < n and np.isfinite(sa[j]) and np.isfinite(sb[j]) and bool(sa[j] >= sb[j]) == is_up:
                j += 1
            end = j + 1 if j < n and np.isfinite(sa[j]) and np.isfinite(sb[j]) else j
            if end - i >= 2:
                xs = np.concatenate([x_cloud[i:end], x_cloud[i:end][::-1]])
                ys = np.concatenate([sa[i:end], sb[i:end][::-1]])
                color = "rgba(46, 204, 113, 0.35)" if is_up else "rgba(231, 76, 60, 0.28)"
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=color, line=dict(width=0), showlegend=False, legendgroup="cloud", hoverinfo="skip"))
            i = j

        # Точки A-B-C хранятся по времени свечи -> переводим в текущие x-координаты
        pts = []
        for p in st.session_state.abc_points:
            if p["t"] in df_plot.index:
                pts.append({"x": int(df_plot.index.get_loc(p["t"])), "y": p["y"]})

        if len(pts) == 3:
            A, B, C = pts
            is_up = B["y"] > A["y"]
            if is_up:
                V, N, E, NT = B["y"] + (B["y"] - C["y"]), C["y"] + (B["y"] - A["y"]), B["y"] + (B["y"] - A["y"]), C["y"] + (C["y"] - A["y"])
            else:
                V, N, E, NT = B["y"] - (C["y"] - B["y"]), C["y"] - (A["y"] - B["y"]), B["y"] - (A["y"] - B["y"]), C["y"] - (A["y"] - C["y"])

            colors = {"V": "orange", "N": "green", "E": "red", "NT": "purple"}
            for name, val in {"V": V, "N": N, "E": E, "NT": NT}.items():
                fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text=f"Target {name}: {fmt_price(val)}", annotation_position="right")

            time_ab, time_ac = abs(B["x"] - A["x"]), abs(C["x"] - A["x"])
            fig.add_vline(x=C["x"] + time_ab, line_dash="dot", line_color="blue", annotation_text=f"Taiyosuu A-B ({int(time_ab)})")
            fig.add_vline(x=C["x"] + time_ac, line_dash="dot", line_color="teal", annotation_text=f"Taiyosuu A-C ({int(time_ac)})")

            for k in KIHON_SUU:
                fig.add_vline(x=C["x"] + k - 1, line_dash="dash", line_color="gray", annotation_text=f"Kihon ({k})", opacity=0.35)

            fig.add_trace(go.Scatter(x=[A["x"], B["x"], C["x"]], y=[A["y"], B["y"], C["y"]], mode="lines+markers", line=dict(color="#f39c12", width=2), marker=dict(size=8), name="Wave A-B-C", hovertemplate=f"%{{y:{pfmt}}}<extra>Wave A-B-C</extra>"))

        tick_step = max(1, len(df_plot) // 10)
        fig.update_layout(
            xaxis_rangeslider_visible=False, height=750, template="plotly_white",
            plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            margin=dict(l=20, r=80, t=40, b=120),
            yaxis=dict(side="right", tickformat=tick_fmt(last_close), showgrid=True, gridcolor="#f0f0f0", fixedrange=False),
            xaxis=dict(tickmode="array", tickvals=df_plot["x_idx"].to_numpy()[::tick_step], ticktext=df_plot.index.strftime("%Y-%m-%d %H:%M")[::tick_step], showgrid=True, gridcolor="#f0f0f0", tickangle=45, fixedrange=False),
            hovermode="closest", clickmode="event+select", dragmode="pan",
            font=dict(color="#2c3e50"),
            legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5),
        )

        event = st.plotly_chart(
            fig,
            key=f"chart_{st.session_state.chart_ver}",
            on_select="rerun",
            selection_mode="points",
            config={"scrollZoom": False, "displayModeBar": True},
            theme=None,
            **WIDE,
        )

        if len(st.session_state.abc_points) == 3 and len(pts) < 3:
            st.info("Часть точек A-B-C вышла за пределы видимых 250 свечей — нажмите Clear Points или смените ТФ.")

        if event and event.selection and event.selection.get("points") and len(st.session_state.abc_points) < 3:
            clicked = event.selection["points"][0]
            x_val = clicked.get("x")

            if x_val is not None:
                rows = df_plot.loc[df_plot["x_idx"] == x_val]
                if not rows.empty:
                    row = rows.iloc[0]
                    curve = clicked.get("curve_number", clicked.get("curveNumber"))
                    price = None  # по умолчанию — клик по линии Ишимоку/Чикоу игнорируется

                    if curve in (1, 3):      # Minor/Major High
                        price = float(row["High"])
                    elif curve in (2, 4):    # Minor/Major Low
                        price = float(row["Low"])
                    elif curve == 0:         # свеча: ближайший экстремум к точке клика
                        y_val = clicked.get("y")
                        if y_val is None or abs(float(y_val) - row["High"]) <= abs(float(y_val) - row["Low"]):
                            price = float(row["High"])
                        else:
                            price = float(row["Low"])

                    if price is not None and not any(p["t"] == row.name for p in st.session_state.abc_points):
                        st.session_state.abc_points.append({"t": row.name, "y": price})
                        st.rerun()
        gc.collect()
