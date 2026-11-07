import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Свечи Twelve Data по форексу по умолчанию собраны в Australia/Sydney и идут 24/7,
# включая субботу. MT5 режет сессию и ставит дневную границу на 17:00 Нью-Йорка
# (сервер обычно UTC+2 зимой и UTC+3 летом). Ниже сырые бары пересобираются
# в эту сетку, иначе H1/D1 и Ишимоку не совпадут с терминалом.

API_KEY = st.secrets["TWELVEDATA_KEY"]

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown("<h3 style='text-align: center; color: #2c3e50;'>Ichimoku Wave Terminal</h3>", unsafe_allow_html=True)

if "abc_points" not in st.session_state:
    st.session_state.abc_points = []

ASSETS = {
    "EUR/USD": "EUR/USD", "USD/JPY": "USD/JPY", "GBP/USD": "GBP/USD",
    "AUD/USD": "AUD/USD", "NZD/USD": "NZD/USD", "EUR/JPY": "EUR/JPY",
    "GBP/JPY": "GBP/JPY", "EUR/AUD": "EUR/AUD",
    "XAU/USD (Gold)": "XAU/USD", "BTC/USD (Bitcoin)": "BTC/USD",
    "SPX500": "SPX", "GER40 (DAX)": "GDAXI", "JPN225": "N225",
}

TF_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H2": "2h", "H4": "4h", "D1": "1day", "W1": "1week", "MN1": "1month",
}
# Из какого интервала пересобирать свечи. H4 и D1 нельзя брать готовыми:
# их границы у провайдера не совпадают с полуночью сервера MT5.
BASE_INTERVAL = {
    "M1": "1min", "M5": "5min", "M15": "5min", "M30": "5min",
    "H1": "1h", "H2": "1h", "H4": "1h", "D1": "1h",
    "W1": "1week", "MN1": "1month",
}
RESAMPLE_RULE = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H2": "2h", "H4": "4h", "D1": "1D", "W1": "W-MON",
}
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]


def server_offset_hours(choice: str) -> int:
    if choice == "UTC+2":
        return 2
    if choice == "UTC+3":
        return 3
    if choice == "UTC":
        return 0
    return int(datetime.now(ZoneInfo("Europe/Bucharest")).utcoffset().total_seconds() // 3600)


def is_fx(symbol: str) -> bool:
    return "/" in symbol and not symbol.startswith("BTC")


def fmt_price(price: float) -> str:
    if price >= 1000:
        return f"{price:.2f}"
    if price >= 10:
        return f"{price:.3f}"
    return f"{price:.5f}"


def fetch_raw(symbol: str, interval: str, outputsize: int = 5000, tz: str | None = "UTC"):
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": API_KEY,
        "outputsize": outputsize,
        "order": "ASC",
    }
    # Без timezone форекс приходит в Australia/Sydney и это нельзя сравнивать с MT5.
    # Для W1/MN1 таймзону не трогаем: эти свечи у вас уже совпадали с терминалом.
    if tz:
        params["timezone"] = tz
    response = requests.get("https://api.twelvedata.com/time_series", params=params, timeout=30)
    payload = response.json()
    if "values" not in payload:
        return pd.DataFrame(), payload.get("message") or str(payload)
    df = pd.DataFrame(payload["values"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=bool(tz))
    df = df.set_index("datetime").sort_index()
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["high"] >= df["low"]) & (df["close"] > 0)]
    df = df.groupby(level=0).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    )
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    return df, None


def forex_session(df_utc: pd.DataFrame, offset: int, drop_weekend: bool, drop_clearing: bool) -> pd.DataFrame:
    """Убрать часы, когда межбанка нет.

    Воскресенье после открытия (17:00 Нью-Йорка) остаётся: в MT5 это уже понедельник,
    и это живая сессия. Суббота и ночь после пятничного клиринга — не шестой
    торговый день Хосоды, а простой рынка.
    """
    if df_utc.empty or not (drop_weekend or drop_clearing):
        return df_utc
    minutes = np.asarray(df_utc.index.hour * 60 + df_utc.index.minute)
    dow = np.asarray(df_utc.index.dayofweek)
    closed = np.zeros(len(df_utc), dtype=bool)
    if drop_weekend:
        close_min = ((24 - offset) % 24) * 60
        closed = (dow == 5) | ((dow == 4) & (minutes >= close_min)) | ((dow == 6) & (minutes < close_min))
    if drop_clearing and offset != 0:
        break_min = ((23 - offset) % 24) * 60
        clearing = (minutes >= break_min) & (minutes < break_min + 60)
        closed = np.asarray(closed) | np.asarray(clearing)
    keep = np.asarray(closed) == False
    return df_utc.iloc[np.flatnonzero(keep)]


def to_server_naive(df_utc: pd.DataFrame, offset: int) -> pd.DataFrame:
    if df_utc.empty:
        return df_utc
    server = timezone(timedelta(hours=offset))
    out = df_utc.copy()
    out.index = df_utc.index.tz_convert(server).tz_localize(None)
    return out


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = (
        df.resample(rule, origin="start_day", label="left", closed="left")
        .agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
        .dropna()
    )
    return out[(out["High"] >= out["Low"]) & (out["Close"] > 0)]


@st.cache_data(ttl=60)
def load_chart(symbol: str, tf_name: str, offset: int, drop_weekend: bool, drop_clearing: bool):
    rebuild = is_fx(symbol) and tf_name not in ("W1", "MN1")
    base = BASE_INTERVAL[tf_name] if rebuild else TF_MAP[tf_name]
    raw, err = fetch_raw(symbol, base, tz="UTC" if rebuild else None)
    if err or raw.empty:
        raw, err = fetch_raw(symbol, base, outputsize=400, tz="UTC" if rebuild else None)
        if err or raw.empty:
            return pd.DataFrame(), err or "пустой ответ", 0

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
    return raw, None, dropped


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    prev = out["Close"].shift(1)
    tr = pd.concat(
        [(out["High"] - out["Low"]), (out["High"] - prev).abs(), (out["Low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    out["ATR"] = tr.rolling(14).mean()
    high, low = out["High"], out["Low"]
    out["tenkan"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    out["kijun"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    out["raw_senkou_a"] = (out["tenkan"] + out["kijun"]) / 2
    out["raw_senkou_b"] = (high.rolling(52).max() + low.rolling(52).min()) / 2
    out["Minor_High"] = (high > high.shift(1)) & (high > high.shift(2)) & (high > high.shift(-1)) & (high > high.shift(-2))
    out["Minor_Low"] = (low < low.shift(1)) & (low < low.shift(2)) & (low < low.shift(-1)) & (low < low.shift(-2))
    out["Major_High"] = True
    out["Major_Low"] = True
    for i in range(1, 11):
        out["Major_High"] &= (high > high.shift(i)) & (high > high.shift(-i))
        out["Major_Low"] &= (low < low.shift(i)) & (low < low.shift(-i))
    return out


def marker_y(price: pd.Series, atr: pd.Series, direction: int, factor: float) -> pd.Series:
    span = atr.fillna((price.diff().abs()).median() or 0)
    return price + direction * span * factor


def add_dots(fig, frame, price_col, direction, factor, size, color, name, kind):
    if frame.empty:
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers", name=name))
        return
    y = marker_y(frame[price_col], frame["ATR"], direction, factor)
    custom = np.column_stack([frame[price_col].to_numpy(), np.full(len(frame), kind)])
    fig.add_trace(go.Scatter(
        x=frame["x_idx"],
        y=y,
        mode="markers",
        marker=dict(size=size, color=color),
        name=name,
        customdata=custom,
        hovertemplate=f"{'Хай' if kind == 'H' else 'Лоу'} %{{customdata[0]:.5f}}<extra>{name}</extra>",
    ))


def resolve_click(point, df_plot):
    """Цена для расчёта — хай или лоу свечи, не координата точки на экране.

    Точки нарочно отодвинуты от свечи на долю ATR, чтобы их было видно.
    y клика — это уже сдвинутая координата, для целей V/N/E она не годится.
    """
    x = point.get("x")
    if x is None:
        return None
    rows = df_plot.loc[df_plot["x_idx"] == x]
    if rows.empty:
        return None
    row = rows.iloc[0]
    curve = point.get("curveNumber", point.get("curve_number"))
    custom = point.get("customdata")
    kind = None
    if isinstance(custom, (list, tuple)) and len(custom) >= 2:
        kind = str(custom[1])
    if kind == "H" or curve in (1, 3):
        return float(row["High"])
    if kind == "L" or curve in (2, 4):
        return float(row["Low"])
    if curve == 0:
        y = point.get("y")
        if y is None or abs(float(y) - row["High"]) <= abs(float(y) - row["Low"]):
            return float(row["High"])
        return float(row["Low"])
    return None


with st.sidebar:
    st.header("Настройки")
    asset_name = st.selectbox("Символ:", list(ASSETS.keys()), index=0)
    tf_name = st.selectbox("Таймфрейм:", list(TF_MAP.keys()), index=4)
    offset_choice = st.selectbox(
        "Время сервера MT5",
        ["Авто (EET)", "UTC+2", "UTC+3", "UTC"],
        index=0,
        help="Зимой большинство серверов UTC+2, летом UTC+3. Сверьте с часами в шапке MetaTrader.",
    )
    count_weekend = st.checkbox(
        "Считать субботу и ночь закрытия",
        value=False,
        help="Хосода считал 6 живых сессий, включая субботу биржи. У форекса в субботу рынка нет: это чужие тики с огромным фитилём.",
    )
    drop_clearing = st.checkbox("Убирать час клиринга 23:00 сервера", value=False)
    offset = server_offset_hours(offset_choice)

    st.markdown("---")
    st.write(f"**Точек волны:** {len(st.session_state.abc_points)}/3")
    if st.button("Очистить точки A-B-C", use_container_width=True):
        st.session_state.abc_points = []
        st.rerun()

    labels = ["A (Старт)", "B (Вершина/Дно)", "C (Откат)"]
    for i in range(3):
        if i < len(st.session_state.abc_points):
            val = st.session_state.abc_points[i]["y"]
            st.success(f"**Точка {labels[i]}:** {fmt_price(val)}")
        else:
            st.info(f"Ожидаю точку {labels[i]}...")

ticker = ASSETS[asset_name]
df, err, dropped = load_chart(ticker, tf_name, offset, not count_weekend, drop_clearing)

if err:
    st.error(f"Twelve Data: {err}")
elif df.empty:
    st.warning("Нет данных после фильтра сессии.")
else:
    df = add_indicators(df)
    df_plot = df.tail(250).copy()
    df_plot["x_idx"] = np.arange(len(df_plot))
    last = df_plot.index[-1]
    if is_fx(ticker) and tf_name not in ("W1", "MN1"):
        st.caption(
            f"Последняя свеча: {last} (сервер UTC{offset:+d}). "
            f"Суббота {'в расчёте' if count_weekend else 'убрана'}. "
        )
    else:
        st.caption(f"Последняя свеча: {last}. Неделя, месяц и не-форекс идут свечами провайдера.")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_plot["x_idx"],
        open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
        increasing_line_color="#2c3e50", increasing_fillcolor="white", increasing_line_width=1,
        decreasing_line_color="#2c3e50", decreasing_fillcolor="#2c3e50", decreasing_line_width=1,
        name="Свечи",
    ))

    # Порядок первых пяти трейсов важен: по нему клик понимает, хай это или лоу.
    add_dots(fig, df_plot[df_plot["Minor_High"] & df_plot["Major_High"].eq(False)], "High", +1, 0.20, 5, "#95a5a6", "Minor High", "H")
    add_dots(fig, df_plot[df_plot["Minor_Low"] & df_plot["Major_Low"].eq(False)], "Low", -1, 0.20, 5, "#95a5a6", "Minor Low", "L")
    add_dots(fig, df_plot[df_plot["Major_High"]], "High", +1, 0.50, 10, "#2c3e50", "Major High", "H")
    add_dots(fig, df_plot[df_plot["Major_Low"]], "Low", -1, 0.50, 10, "#2c3e50", "Major Low", "L")

    fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["tenkan"], line=dict(color="#2980b9", width=1.5), name="Tenkan"))
    fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["kijun"], line=dict(color="#e74c3c", width=2), name="Kijun"))
    fig.add_trace(go.Scatter(
        x=df_plot["x_idx"] - 26, y=df_plot["Close"],
        line=dict(color="#1e8449", width=1.2), name="Chikou",
    ))

    x_cloud = np.arange(26, len(df_plot) + 26)
    sa = df_plot["raw_senkou_a"].to_numpy()
    sb = df_plot["raw_senkou_b"].to_numpy()
    for bull, color, title in (
        (True, "rgba(46, 204, 113, 0.25)", "Kumo+"),
        (False, "rgba(231, 76, 60, 0.20)", "Kumo-"),
    ):
        mask = sa >= sb if bull else sa < sb
        fig.add_trace(go.Scatter(x=x_cloud, y=np.where(mask, sa, np.nan), line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=x_cloud, y=np.where(mask, sb, np.nan),
            fill="tonexty", fillcolor=color, line=dict(width=0), name=title, hoverinfo="skip",
        ))

    if len(st.session_state.abc_points) == 3:
        A, B, C = st.session_state.abc_points
        is_up = B["y"] > A["y"]
        if is_up:
            V = B["y"] + (B["y"] - C["y"])
            N = C["y"] + (B["y"] - A["y"])
            E = B["y"] + (B["y"] - A["y"])
            NT = C["y"] + (C["y"] - A["y"])
        else:
            V = B["y"] - (C["y"] - B["y"])
            N = C["y"] - (A["y"] - B["y"])
            E = B["y"] - (A["y"] - B["y"])
            NT = C["y"] - (A["y"] - C["y"])
        colors = {"V": "orange", "N": "green", "E": "red", "NT": "purple"}
        for name, val in {"V": V, "N": N, "E": E, "NT": NT}.items():
            fig.add_hline(
                y=val, line_dash="dash", line_color=colors[name],
                annotation_text=f"Цель {name}: {fmt_price(val)}", annotation_position="right",
            )
        time_ab = abs(B["x"] - A["x"])
        time_ac = abs(C["x"] - A["x"])
        fig.add_vline(x=C["x"] + time_ab, line_dash="dot", line_color="blue", annotation_text=f"Тайёсуу A-B ({int(time_ab)})")
        fig.add_vline(x=C["x"] + time_ac, line_dash="dot", line_color="teal", annotation_text=f"Тайёсуу A-
