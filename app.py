import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Twelve Data отдает форекс в поясе Sydney и рисует субботу.
# Ниже бары переводятся в время сервера MT5 (UTC+2 зимой, UTC+3 летом).

API_KEY = st.secrets["TWELVEDATA_KEY"]

st.set_page_config(page_title="Ichimoku Pro Terminal", layout="wide")
st.markdown(
    "<h3 style='text-align: center; color: #2c3e50;'>"
    "Ichimoku Wave Terminal</h3>",
    unsafe_allow_html=True,
)

if "abc_points" not in st.session_state:
    st.session_state.abc_points = []

ASSETS = {
    "EUR/USD": "EUR/USD",
    "USD/JPY": "USD/JPY",
    "GBP/USD": "GBP/USD",
    "AUD/USD": "AUD/USD",
    "NZD/USD": "NZD/USD",
    "EUR/JPY": "EUR/JPY",
    "GBP/JPY": "GBP/JPY",
    "EUR/AUD": "EUR/AUD",
    "XAU/USD (Gold)": "XAU/USD",
    "BTC/USD (Bitcoin)": "BTC/USD",
    "SPX500": "SPX",
    "GER40 (DAX)": "GDAXI",
    "JPN225": "N225",
}

TF_MAP = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H2": "2h",
    "H4": "4h",
    "D1": "1day",
    "W1": "1week",
    "MN1": "1month",
}
BASE_INTERVAL = {
    "M1": "1min",
    "M5": "5min",
    "M15": "5min",
    "M30": "5min",
    "H1": "1h",
    "H2": "1h",
    "H4": "1h",
    "D1": "1h",
    "W1": "1week",
    "MN1": "1month",
}
RESAMPLE_RULE = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H2": "2h",
    "H4": "4h",
    "D1": "1D",
    "W1": "W-MON",
}
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]


def server_offset_hours(choice):
    if choice == "UTC+2":
        return 2
    if choice == "UTC+3":
        return 3
    if choice == "UTC":
        return 0
    zone = ZoneInfo("Europe/Bucharest")
    delta = datetime.now(zone).utcoffset().total_seconds()
    return int(delta // 3600)


def is_fx(symbol):
    if symbol.startswith("BTC"):
        return False
    return "/" in symbol


def fmt_price(price):
    if price >= 1000:
        return f"{price:.2f}"
    if price >= 10:
        return f"{price:.3f}"
    return f"{price:.5f}"


def fetch_raw(symbol, interval, outputsize=5000, tz="UTC"):
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": API_KEY,
        "outputsize": outputsize,
        "order": "ASC",
    }
    if tz:
        params["timezone"] = tz
    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params=params,
        timeout=30,
    )
    payload = response.json()
    if "values" not in payload:
        message = payload.get("message") or str(payload)
        return pd.DataFrame(), message
    df = pd.DataFrame(payload["values"])
    df["datetime"] = pd.to_datetime(df["datetime"], utc=bool(tz))
    df = df.set_index("datetime").sort_index()
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    good = (df["high"] >= df["low"]) & (df["close"] > 0)
    df = df.loc[good]
    df = df.groupby(level=0).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    )
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
        }
    )
    return df, None


def forex_session(df_utc, offset, drop_weekend, drop_clearing):
    # Суббота и ночь после пятничного закрытия — простой рынка.
    # Воскресенье после 17:00 Нью-Йорка остается: в MT5 это понедельник.
    if df_utc.empty or not (drop_weekend or drop_clearing):
        return df_utc
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
    if df_utc.empty:
        return df_utc
    server = timezone(timedelta(hours=offset))
    out = df_utc.copy()
    out.index = df_utc.index.tz_convert(server).tz_localize(None)
    return out


def resample_ohlc(df, rule):
    if df.empty:
        return df
    out = df.resample(rule, origin="start_day", label="left", closed="left")
    out = out.agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
    ).dropna()
    good = (out["High"] >= out["Low"]) & (out["Close"] > 0)
    return out.loc[good]


@st.cache_data(ttl=60)
def load_chart(symbol, tf_name, offset, drop_weekend, drop_clearing):
    rebuild = is_fx(symbol) and tf_name not in ("W1", "MN1")
    if rebuild:
        base = BASE_INTERVAL[tf_name]
        zone = "UTC"
    else:
        base = TF_MAP[tf_name]
        zone = None
    raw, err = fetch_raw(symbol, base, tz=zone)
    if err or raw.empty:
        raw, err = fetch_raw(symbol, base, outputsize=400, tz=zone)
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


def add_indicators(df):
    out = df.copy()
    prev = out["Close"].shift(1)
    tr = pd.concat(
        [
            out["High"] - out["Low"],
            (out["High"] - prev).abs(),
            (out["Low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["ATR"] = tr.rolling(14).mean()
    high = out["High"]
    low = out["Low"]
    out["tenkan"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    out["kijun"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    out["raw_senkou_a"] = (out["tenkan"] + out["kijun"]) / 2
    span = high.rolling(52).max() + low.rolling(52).min()
    out["raw_senkou_b"] = span / 2
    above_l = (high > high.shift(1)) & (high > high.shift(2))
    above_r = (high > high.shift(-1)) & (high > high.shift(-2))
    below_l = (low < low.shift(1)) & (low < low.shift(2))
    below_r = (low < low.shift(-1)) & (low < low.shift(-2))
    out["Minor_High"] = above_l & above_r
    out["Minor_Low"] = below_l & below_r
    out["Major_High"] = True
    out["Major_Low"] = True
    for i in range(1, 11):
        out["Major_High"] = out["Major_High"] & (high > high.shift(i))
        out["Major_High"] = out["Major_High"] & (high > high.shift(-i))
        out["Major_Low"] = out["Major_Low"] & (low < low.shift(i))
        out["Major_Low"] = out["Major_Low"] & (low < low.shift(-i))
    return out


def marker_y(price, atr, direction, factor):
    span = atr.fillna(price.diff().abs().median() or 0)
    return price + direction * span * factor


def add_dots(fig, frame, price_col, direction, factor, size, color, name, kind):
    if frame.empty:
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers", name=name))
        return
    y = marker_y(frame[price_col], frame["ATR"], direction, factor)
    prices = frame[price_col].to_numpy()
    kinds = np.full(len(frame), kind)
    custom = np.column_stack([prices, kinds])
    if kind == "H":
        tip = "Хай %{customdata[0]:.5f}<extra>" + name + "</extra>"
    else:
        tip = "Лоу %{customdata[0]:.5f}<extra>" + name + "</extra>"
    fig.add_trace(
        go.Scatter(
            x=frame["x_idx"],
            y=y,
            mode="markers",
            marker=dict(size=size, color=color),
            name=name,
            customdata=custom,
            hovertemplate=tip,
        )
    )


def resolve_click(point, df_plot):
    # В расчет идет хай или лоу свечи, не сдвинутая точка на экране.
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
        if y is None:
            return float(row["High"])
        dist_high = abs(float(y) - row["High"])
        dist_low = abs(float(y) - row["Low"])
        if dist_high <= dist_low:
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
    )
    count_weekend = st.checkbox("Считать субботу и ночь закрытия", value=False)
    drop_clearing = st.checkbox("Убирать час клиринга 23:00", value=False)
    offset = server_offset_hours(offset_choice)
    st.markdown("---")
    st.write("Точек волны: " + str(len(st.session_state.abc_points)) + "/3")
    if st.button("Очистить точки A-B-C", use_container_width=True):
        st.session_state.abc_points = []
        st.rerun()
    labels = ["A (Старт)", "B (Вершина/Дно)", "C (Откат)"]
    for i in range(3):
        if i < len(st.session_state.abc_points):
            val = st.session_state.abc_points[i]["y"]
            st.success("Точка " + labels[i] + ": " + fmt_price(val))
        else:
            st.info("Ожидаю точку " + labels[i])

ticker = ASSETS[asset_name]
df, err, dropped = load_chart(
    ticker,
    tf_name,
    offset,
    not count_weekend,
    drop_clearing,
)

if err:
    st.error("Twelve Data: " + str(err))
elif df.empty:
    st.warning("Нет данных после фильтра сессии.")
else:
    df = add_indicators(df)
    df_plot = df.tail(250).copy()
    df_plot["x_idx"] = np.arange(len(df_plot))
    last = df_plot.index[-1]
    if is_fx(ticker) and tf_name not in ("W1", "MN1"):
        if count_weekend:
            sat = "в расчете"
        else:
            sat = "убрана"
        st.caption(
            "Последняя свеча: "
            + str(last)
            + " (сервер UTC"
            + format(offset, "+d")
            + "). Суббота "
            + sat
            + "."
        )
    else:
        st.caption("Последняя свеча: " + str(last) + ". Свечи провайдера.")

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df_plot["x_idx"],
            open=df_plot["Open"],
            high=df_plot["High"],
            low=df_plot["Low"],
            close=df_plot["Close"],
            increasing_line_color="#2c3e50",
            increasing_fillcolor="white",
            increasing_line_width=1,
            decreasing_line_color="#2c3e50",
            decreasing_fillcolor="#2c3e50",
            decreasing_line_width=1,
            name="Свечи",
        )
    )

    minor_high = df_plot["Minor_High"] & df_plot["Major_High"].eq(False)
    minor_low = df_plot["Minor_Low"] & df_plot["Major_Low"].eq(False)
    add_dots(fig, df_plot.loc[minor_high], "High", 1, 0.20, 5, "#95a5a6", "Minor High", "H")
    add_dots(fig, df_plot.loc[minor_low], "Low", -1, 0.20, 5, "#95a5a6", "Minor Low", "L")
    major_high = df_plot.loc[df_plot["Major_High"]]
    major_low = df_plot.loc[df_plot["Major_Low"]]
    add_dots(fig, major_high, "High", 1, 0.50, 10, "#2c3e50", "Major High", "H")
    add_dots(fig, major_low, "Low", -1, 0.50, 10, "#2c3e50", "Major Low", "L")

    fig.add_trace(
        go.Scatter(
            x=df_plot["x_idx"],
            y=df_plot["tenkan"],
            line=dict(color="#2980b9", width=1.5),
            name="Tenkan",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_plot["x_idx"],
            y=df_plot["kijun"],
            line=dict(color="#e74c3c", width=2),
            name="Kijun",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_plot["x_idx"] - 26,
            y=df_plot["Close"],
            line=dict(color="#1e8449", width=1.2),
            name="Chikou",
        )
    )

    x_cloud = np.arange(len(df_plot)) + 26
    sa = df_plot["raw_senkou_a"].to_numpy(dtype=float)
    sb = df_plot["raw_senkou_b"].to_numpy(dtype=float)
    shown_up = False
    shown_dn = False
    i = 0
    n = len(sa)
    while i < n:
        if not (np.isfinite(sa[i]) and np.isfinite(sb[i])):
            i += 1
            continue
        is_up = bool(sa[i] >= sb[i])
        j = i + 1
        while j < n:
            if not (np.isfinite(sa[j]) and np.isfinite(sb[j])):
                break
            if bool(sa[j] >= sb[j]) != is_up:
                break
            j += 1
        end = j
        if j < n and np.isfinite(sa[j]) and np.isfinite(sb[j]):
            end = j + 1
        if end - i >= 2:
            xs = np.concatenate([x_cloud[i:end], x_cloud[i:end][::-1]])
            ys = np.concatenate([sa[i:end], sb[i:end][::-1]])
            if is_up:
                color = "rgba(46, 204, 113, 0.35)"
                title = "Kumo+"
                show = not shown_up
                shown_up = True
            else:
                color = "rgba(231, 76, 60, 0.28)"
                title = "Kumo-"
                show = not shown_dn
                shown_dn = True
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="lines",
                    fill="toself",
                    fillcolor=color,
                    line=dict(width=0),
                    name=title,
                    showlegend=show,
                    hoverinfo="skip",
                )
            )
        i = j
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
        targets = {"V": V, "N": N, "E": E, "NT": NT}
        for name, val in targets.items():
            fig.add_hline(
                y=val,
                line_dash="dash",
                line_color=colors[name],
                annotation_text="Цель " + name + ": " + fmt_price(val),
                annotation_position="right",
            )
        time_ab = abs(B["x"] - A["x"])
        time_ac = abs(C["x"] - A["x"])
        fig.add_vline(
            x=C["x"] + time_ab,
            line_dash="dot",
            line_color="blue",
            annotation_text="Тайёсуу A-B (" + str(int(time_ab)) + ")",
        )
        fig.add_vline(
            x=C["x"] + time_ac,
            line_dash="dot",
            line_color="teal",
            annotation_text="Тайёсуу A-C (" + str(int(time_ac)) + ")",
        )
        for k in KIHON_SUU:
            fig.add_vline(
                x=C["x"] + k - 1,
                line_dash="dash",
                line_color="gray",
                annotation_text="Кихон (" + str(k) + ")",
                opacity=0.35,
            )
        fig.add_trace(
            go.Scatter(
                x=[A["x"], B["x"], C["x"]],
                y=[A["y"], B["y"], C["y"]],
                mode="lines+markers",
                line=dict(color="gold", width=3),
                marker=dict(size=10),
                name="Волна A-B-C",
            )
        )

    tick_step = max(1, len(df_plot) // 10)
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=750,
        template="plotly_white",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        margin=dict(l=20, r=80, t=40, b=40),
        yaxis=dict(
            side="right",
            tickformat=".5f",
            showgrid=True,
            gridcolor="#f0f0f0",
            fixedrange=False,
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=df_plot["x_idx"].to_numpy()[::tick_step],
            ticktext=df_plot.index.strftime("%Y-%m-%d %H:%M")[::tick_step],
            showgrid=True,
            gridcolor="#f0f0f0",
            tickangle=45,
            fixedrange=False,
        ),
        hovermode="closest",
        clickmode="event+select",
        dragmode="pan",
    )
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        config={"scrollZoom": False, "displayModeBar": True},
    )
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
