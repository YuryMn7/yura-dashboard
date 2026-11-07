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
# 1. КОНСТАНТЫ И МАРШРУТИЗАЦИЯ
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
    "SPX500": {"prov": "yahoo", "sym": "^GSPC", "yf": "^GSPC"},
    "GER40 (DAX)": {"prov": "yahoo", "sym": "^GDAXI", "yf": "^GDAXI"},
    "JPN225": {"prov": "yahoo", "sym": "^N225", "yf": "^N225"},
    "AUS200": {"prov": "yahoo", "sym": "^AXJO", "yf": "^AXJO"}
}

TF_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", 
    "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h", 
    "D1": "1day", "W1": "1week", "MN1": "1month", "MN6": "6month", "MN24": "24month"
}
RESAMPLE_RULE = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", 
    "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h", 
    "D1": "1D", "W1": "W-MON", "MN6": "6MS", "MN24": "24MS"
}
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]

# ==========================================
# 2. ЯДРО ОБРАБОТКИ ДАННЫХ
# ==========================================
def resample_ohlc(df, rule):
    if df.empty: return df
    out = df.resample(rule, origin="start_day", label="left", closed="left")
    out = out.agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last")).dropna()
    return out.loc[(out["High"] >= out["Low"]) & (out["Close"] > 0)]

def fetch_yahoo(sym, interval):
    yf_int = interval
    per = "2y"
    if interval == "M1": yf_int = "1m"; per = "5d"
    elif interval in ["M5", "M15", "M30"]: yf_int = interval.lower(); per = "60d"
    elif interval in ["H1", "H2", "H4", "H8"]: yf_int = "1h"; per = "700d"
    elif interval == "D1": yf_int = "1d"; per = "10y"
    elif interval == "W1": yf_int = "1wk"; per = "15y"
    elif interval in ["MN1", "MN6", "MN24"]: y_int = "1mo"; per = "max"
    
    try:
        df = yf.download(sym, period=per, interval=yf_int, progress=False)
        if df.empty: return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=lambda x: x.capitalize())
        df.index = df.index.tz_localize("UTC") if getattr(df.index, "tz", None) is None else df.index.tz_convert("UTC")
        if interval in ["H2", "H4", "H8", "MN6", "MN24"]: df = resample_ohlc(df, RESAMPLE_RULE[interval])
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_smart_data(asset_key, interval):
    route = ASSET_ROUTER[asset_key]
    provider, sym = route["prov"], route["sym"]
    
    if provider == "yahoo":
        return fetch_yahoo(route["yf"], interval)
        
    try:
        base_int = TF_MAP.get(interval, "1h")
        if interval in ["H2", "H4", "H8"]: base_int = "1h"
        elif interval in ["MN6", "MN24"]: base_int = "1month"
        
        url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval={base_int}&apikey={API_KEY}&outputsize=5000"
        res = requests.get(url, timeout=10).json()
        if 'values' not in res: return pd.DataFrame()
        
        df = pd.DataFrame(res['values'])
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df = df.set_index('datetime').sort_index()
        for col in ['open', 'high', 'low', 'close']: df[col] = pd.to_numeric(df[col], errors="coerce")
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
        df = df.dropna()
        
        if interval in ["H2", "H4", "H8", "MN6", "MN24"]: df = resample_ohlc(df, RESAMPLE_RULE[interval])
        return df
    except: return pd.DataFrame()

def add_indicators(df):
    out = df.copy()
    prev = out["Close"].shift(1)
    out["ATR"] = pd.concat([out["High"] - out["Low"], (out["High"] - prev).abs(), (out["Low"] - prev).abs()], axis=1).max(axis=1).rolling(14).mean()
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

# ==========================================
# 3. НАВИГАЦИЯ И ИНТЕРФЕЙС
# ==========================================
with st.sidebar:
    st.markdown("### Navigation")
    app_mode = st.radio("Select Module:", ["Market Scanner (Radar)", "Analytical Terminal"])

if app_mode == "Market Scanner (Radar)":
    st.markdown("<h2 style='color: #2c3e50;'>Global Market Scanner</h2>", unsafe_allow_html=True)
    radar_tf = st.selectbox("Select Timeframe:", ["M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1", "MN6", "MN24"], index=4)
    
    if st.button("Execute Market Scan", use_container_width=True):
        progress_text = "Scanning market data..."
        my_bar = st.progress(0, text=progress_text)
        radar_results = []
        
        RADAR_HTF_MAP = {"M15": "H4", "M30": "H4", "H1": "D1", "H2": "D1", "H4": "W1", "H8": "W1", "D1": "MN1", "W1": "MN1", "MN1": "MN1", "MN6": "MN24", "MN24": "MN24"}
        htf_radar = RADAR_HTF_MAP.get(radar_tf, "MN1")
        
        for i, (asset_name, route) in enumerate(ASSET_ROUTER.items()):
            my_bar.progress((i + 1) / len(ASSET_ROUTER), text=f"Processing {asset_name}...")
            try:
                df_ltf = fetch_yahoo(route["yf"], radar_tf)
                df_htf = fetch_yahoo(route["yf"], htf_radar)
                
                if df_ltf.empty or df_htf.empty or len(df_ltf) < 26 or len(df_htf) < 26: continue
                
                df_ltf = add_indicators(df_ltf)
                df_htf = add_indicators(df_htf)
                
                h_c = df_htf.iloc[-2]
                # 🛠 ИСПРАВЛЕНИЕ ЛОГИКИ ТРЕНДА: Используем senkou_a и senkou_b (Текущее облако)
                kumo_top = max(float(h_c["senkou_a"]), float(h_c["senkou_b"]))
                kumo_bot = min(float(h_c["senkou_a"]), float(h_c["senkou_b"]))
                
                is_bull = float(h_c["Close"]) > kumo_top and float(h_c["tenkan"]) >= float(h_c["kijun"])
                is_bear = float(h_c["Close"]) < kumo_bot and float(h_c["tenkan"]) <= float(h_c["kijun"])
                trend = "BULLISH" if is_bull else ("BEARISH" if is_bear else "FLAT")
                
                l_c = df_ltf.iloc[-2]
                pr, kijun = float(l_c["Close"]), float(l_c["kijun"])
                near = abs(pr - kijun) <= (float(l_c["ATR"]) * 0.3)
                sig = "BUY" if near and is_bull and float(l_c["tenkan"]) > kijun else ("SELL" if near and is_bear and float(l_c["tenkan"]) < kijun else "WAIT")
                
                radar_results.append({"Asset": asset_name, "HTF Trend": trend, "Signal (Kijun)": sig, "Price": f"{pr:.5f}"})
            except: pass
            
        my_bar.empty()
        if radar_results: st.dataframe(pd.DataFrame(radar_results), use_container_width=True, hide_index=True)
        else: st.warning("Scan completed. No valid data retrieved.")

elif app_mode == "Analytical Terminal":
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Terminal Settings")
        asset_name = st.selectbox("Symbol:", list(ASSET_ROUTER.keys()), index=0)
        tf_name = st.selectbox("Timeframe:", list(TF_MAP.keys()), index=4)
        
        st.markdown("---")
        st.markdown("### Wave Points (A-B-C)")
        labels = ["A (Start)", "B (Peak/Trough)", "C (Retracement)"]
        for i in range(3):
            if i < len(st.session_state.abc_points): st.success(f"{labels[i]}: {st.session_state.abc_points[i]['y']:.5f}")
            else: st.info(f"Awaiting {labels[i]}...")
        if st.button("Clear Points", use_container_width=True):
            st.session_state.abc_points = []
            st.rerun()

    df_raw = fetch_smart_data(asset_name, tf_name)

    if df_raw.empty:
        st.warning("Market data is currently unavailable.")
    else:
        df = add_indicators(df_raw)
        df_plot = df.tail(250).copy()
        df_plot["x_idx"] = np.arange(len(df_plot))
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_plot["x_idx"], open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
            increasing_line_color="#2c3e50", increasing_fillcolor="white", increasing_line_width=1,
            decreasing_line_color="#2c3e50", decreasing_fillcolor="#2c3e50", decreasing_line_width=1, name="Price"
        ))

        # Фракталы
        minor_high = df_plot["Minor_High"] & ~df_plot["Major_High"]
        minor_low = df_plot["Minor_Low"] & ~df_plot["Major_Low"]
        fig.add_trace(go.Scatter(x=df_plot.loc[minor_high, "x_idx"], y=df_plot.loc[minor_high, "High"] + df_plot.loc[minor_high, "ATR"]*0.2, mode="markers", marker=dict(size=5, color="#95a5a6"), name="Minor High"))
        fig.add_trace(go.Scatter(x=df_plot.loc[minor_low, "x_idx"], y=df_plot.loc[minor_low, "Low"] - df_plot.loc[minor_low, "ATR"]*0.2, mode="markers", marker=dict(size=5, color="#95a5a6"), name="Minor Low"))
        
        major_high = df_plot["Major_High"]
        major_low = df_plot["Major_Low"]
        fig.add_trace(go.Scatter(x=df_plot.loc[major_high, "x_idx"], y=df_plot.loc[major_high, "High"] + df_plot.loc[major_high, "ATR"]*0.5, mode="markers", marker=dict(size=10, color="#2c3e50"), name="Major High"))
        fig.add_trace(go.Scatter(x=df_plot.loc[major_low, "x_idx"], y=df_plot.loc[major_low, "Low"] - df_plot.loc[major_low, "ATR"]*0.5, mode="markers", marker=dict(size=10, color="#2c3e50"), name="Major Low"))

        # Ишимоку
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["tenkan"], line=dict(color="#2980b9", width=1.5), name="Tenkan-sen"))
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["kijun"], line=dict(color="#e74c3c", width=2), name="Kijun-sen"))
        fig.add_trace(go.Scatter(x=df_plot["x_idx"] - 26, y=df_plot["Close"], line=dict(color="#1e8449", width=1.2, dash='dashdot'), name="Chikou Span"))

        x_cloud = np.arange(len(df_plot)) + 26
        sa, sb = df_plot["raw_senkou_a"].to_numpy(dtype=float), df_plot["raw_senkou_b"].to_numpy(dtype=float)
        
        # Облако (Группировка для легенды)
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
                fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text=f"Target {name}: {val:.5f}", annotation_position="right")
            
            time_ab, time_ac = abs(B["x"] - A["x"]), abs(C["x"] - A["x"])
            fig.add_vline(x=C["x"] + time_ab, line_dash="dot", line_color="blue", annotation_text=f"Taiyosuu A-B ({int(time_ab)})")
            fig.add_vline(x=C["x"] + time_ac, line_dash="dot", line_color="teal", annotation_text=f"Taiyosuu A-C ({int(time_ac)})")
            
            for k in KIHON_SUU:
                fig.add_vline(x=C["x"] + k - 1, line_dash="dash", line_color="gray", annotation_text=f"Kihon ({k})", opacity=0.35)
                
            fig.add_trace(go.Scatter(x=[A["x"], B["x"], C["x"]], y=[A["y"], B["y"], C["y"]], mode="lines+markers", line=dict(color="#f39c12", width=2), marker=dict(size=8), name="Wave A-B-C"))

        tick_step = max(1, len(df_plot) // 10)
        fig.update_layout(
            xaxis_rangeslider_visible=False, height=750, template="plotly_white",
            plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            margin=dict(l=20, r=80, t=40, b=120), # 🛠 Отступ для легенды снизу
            yaxis=dict(side="right", tickformat=".5f", showgrid=True, gridcolor="#f0f0f0", fixedrange=False),
            xaxis=dict(tickmode="array", tickvals=df_plot["x_idx"].to_numpy()[::tick_step], ticktext=df_plot.index.strftime("%Y-%m-%d %H:%M")[::tick_step], showgrid=True, gridcolor="#f0f0f0", tickangle=45, fixedrange=False),
            hovermode="closest", clickmode="event+select", dragmode="pan",
            font=dict(color='#2c3e50'),
            legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5) # 🛠 Легенда смещена вниз
        )
        
        event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points", config={"scrollZoom": False, "displayModeBar": True}, theme=None)
        
        if event and event.selection and event.selection.get("points"):
            clicked = event.selection["points"][0]
            x_val = clicked.get("x")
            
            if x_val is not None:
                rows = df_plot.loc[df_plot["x_idx"] == x_val]
                if not rows.empty:
                    row = rows.iloc[0]
                    # 🎯 АБСОЛЮТНАЯ ТОЧНОСТЬ: берем реальный High/Low свечи
                    price = float(row["High"]) if len(st.session_state.abc_points) == 1 else float(row["Low"])
                    if len(st.session_state.abc_points) < 3 and not any(p["x"] == x_val for p in st.session_state.abc_points):
                        st.session_state.abc_points.append({"x": x_val, "y": price})
                        st.rerun()
        gc.collect()
