"""Quantitative Analysis Terminal — Streamlit, монолитный app.py.
SPEC v1.70. Стиль: strict institutional minimalist, zero-clutter, zero-emoji на холсте.
Режим экрана — по User-Agent; язык первой загрузки — по Accept-Language.
Крипта: BTC W1/MN1/MN3 -> старший MN1.

SWING EXTREMUM HARDENING (v1.70): фрактальный детектор использует тай-брейк полярности —
слева нестрогое сравнение (>= / <=), справа строгое (> / <). При двойной вершине или плоском
пике маркер достаётся ПЕРВОМУ появлению экстремума и не теряется на обоих барах.
Дополнительно абсолютные High/Low видимого окна (idxmax / idxmin) принудительно получают
маркер главного фрактала — доминантный экстремум не может быть замаскирован краем окна.

TAP-TO-RESET HUD (v1.70): нижняя статус-пилюля — нативная кнопка pts_bar_btn. Один тап
сбрасывает все точки волны (A, B, C, O) и перерисовывает холст начисто. Геометрия и типографика
совпадают со статичной полосой v1.61; на мобильных пилюля зафиксирована внизу вьюпорта
с pointer-events: auto, поэтому касание срабатывает немедленно.

ANNOTATION DYNAMIC POLARITY (v1.62): подписи точек волны A/B/C и Истока O не имеют статичного
сдвига вверх. Полярность определяется сравнением с High/Low свечи; буква якорится над High
(yshift +14 / yanchor bottom / va bottom) или под Low (yshift -14 / yanchor top / va top).
Реализовано синхронно в Plotly и Matplotlib — веб-холст и Telegram-снапшот одинаково читаемы.

BUGFIX v1.61 (Telegram export pipeline): список точек для Matplotlib-снапшота не обрезается
до трёх (tg_pts = [... for p_ in pts]), поэтому сетка Kihon Suu в Telegram якорится к Истоку.
Развязка сохранена: ценовые цели и AI строго по abc[:3].

4-POINT HOSODA TIME ARCHITECTURE:
  Points 1-3 (A, B, C): первичная геометрия волны, цели V/N/E/NT, коридор Taiyosuu (AB/AC),
  AI Alice инференс, риск-менеджмент и лот-калькуляция.
  Point 4 (O — Origin/Anchor): опциональный исток цикла для сетки Kihon Suu (9, 17, 26, ...).
  Fallback: если O не задан, Kihon Suu якорится к A. AI и Risk строго потребляют abc[:3].

OUTBOUND TELEMETRY (MT5 ➔ Supabase ➔ Streamlit):
  Поллер fetch_account_telemetry() (ttl 4 с) читает последнюю строку public.account_telemetry.
  HUD здоровья счёта в сайдбаре: Account · Balance · Equity · Daily DD (кап 3.0 %) · Total DD · Status.
  Зелёная пульсирующая точка ● LIVE при age < 60 с, ○ OFFLINE иначе.
  Автопривязка: при LIVE account_deposit = equity (поле disabled), при OFFLINE — ручной ввод.

ЛЕГЕНДА-ХАД: фракталы сведены в группы Plotly — minor и major; у каждой группы одна плашка,
остальные трейсы showlegend=False. layout.legend.groupclick="togglegroup" — один клик гасит
всю группу. Облако Кумо работает по той же схеме. Переключение слоёв чисто клиентское.

КНОПКА ОБНОВЛЕНИЯ ↻: наложена на верхнюю полосу графика слева, абсолютное позиционирование
внутри оболочки st.container(key="chart_shell") — ноль строк в потоке.

РАДАР (Real-Time засада у Киджун): тренд/Облако/линии/Чикоу — по закрытому бару (iloc[-2]);
зона засады — по активной свече (iloc[-1]) с порогом 0.3*ATR. Колонка «Причина» — диагностика.
ONE-CLICK TELEPORT: выбор строки в таблице Радара -> перенос в Терминал.

ПРЕДВАРИТЕЛЬНАЯ C: маркер размером с малый фрактал, виден ДО расстановки A-B-C.
Нисходящий тренд (Тенкан < Киджун) — максимум High последних 3 свечей включая активную;
восходящий — минимум Low. Отступ 0.2*ATR, компактный ховер. Клик ставит точку волны.

ГОРИЗОНТ ПРОЕКЦИИ: +76 баров от точки C (канон Какан). Тот же предел в PNG для Telegram.

ВХОДЫ ПО ПРОБОЮ (trigger_plan): «Хосода: разворот C» — уровень High/Low свечи C, окно 3 свечи;
«Пробой точки B» — уровень цены B, окно 17 свечей, стоп за ОБЛАКОМ ± 0.2*ATR.
Подтверждение = ЗАКРЫТИЕ свечи за уровнем. Правило догона: уход <= 1*ATR -> рынок,
дальше -> ЛИМИТНЫЙ ордер на самый уровень. Нет подтверждения -> наблюдение (watch).

АЛИСА — ZERO-LAG: лаг подтверждения убран и в обучении, и в инференсе (ALICE_LAG = 0).
Вход = бар C, все признаки причинны. Edge, вероятности и светофор выдаются сразу при выборе C.

РИСК ПОД BLUE GUARDIAN: дефолт 0.5 % на сделку, шаг ввода 0.1 %.
ЛОТ: pip_value_usd (JPY — 1000 JPY за пипс по курсу USD/JPY; прямые пары — $10; EUR/AUD — 10 AUD
в USD; золото — $100 за пункт; BTC — $1; индексы — $1), округление ВНИЗ до шага 0.01.
ШЛЮЗ: карточка /order {JSON} в Telegram с кнопкой подтверждения; советник получает приказ
только как callback_query после нажатия трейдером. Финальный лот и комплаенс — на стороне советника.

BY DESIGN: точки A-B-C-O сбрасываются при смене инструмента, ТФ, серверного времени, raw, клиринга,
кнопкой «Сбросить точки», тапом по статус-пилюле и при телепорте. Обновление котировок, смена языка
и отчёты точки НЕ сбрасывают.

Зависимости: streamlit, yfinance, pandas, numpy, plotly, requests, scikit-learn (kaleido/matplotlib — опц.).
Секреты: TWELVEDATA_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, MT5_SECRET_TOKEN (опц.),
         SUPABASE_URL, SUPABASE_KEY (опц., для телеметрии MT5).
"""
import gc
import io
import json
import re
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import roc_auc_score
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

st.set_page_config(page_title="Quantitative Analysis Terminal", layout="wide")

API_KEY = st.secrets["TWELVEDATA_KEY"]
_ST_VER = tuple(int(x) for x in re.findall(r"\d+", st.__version__)[:2])
WIDE = {"width": "stretch"} if _ST_VER >= (1, 50) else {"use_container_width": True}

st.session_state.setdefault("abc_points", [])
st.session_state.setdefault("chart_ver", 0)


def reset_points():
    st.session_state.abc_points = []
    st.session_state.chart_ver += 1
    st.session_state.pop("custom_entry", None)


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
    "Индекс Доллара (DXY)": {"prov": "yahoo", "sym": "DXY", "yf": "DX-Y.NYB"},
}
ASSET_LABELS_EN = {"Индекс Доллара (DXY)": "US Dollar Index (DXY)"}

TF_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H2": "2h", "H4": "4h", "H8": "8h",
    "D1": "1day", "W1": "1week", "MN1": "1month", "MN3": "3month", "MN6": "6month", "MN24": "24month",
}
YF_MAP = {
    "M1": ("1m", "5d"),
    "M5": ("5m", "60d"), "M15": ("15m", "60d"), "M30": ("30m", "60d"),
    "H1": ("1h", "700d"), "H2": ("1h", "700d"), "H4": ("1h", "700d"), "H8": ("1h", "700d"),
    "D1": ("1h", "700d"), "W1": ("1wk", "15y"),
    "MN1": ("1mo", "max"), "MN3": ("1mo", "max"), "MN6": ("1mo", "max"), "MN24": ("1mo", "max"),
}
BASE_TF = {"H2": "H1", "H4": "H1", "H8": "H1", "D1": "H1", "MN3": "MN1", "MN6": "MN1", "MN24": "MN1"}
RESAMPLE_RULE = {"H2": "2h", "H4": "4h", "H8": "8h", "D1": "1D", "MN3": "3MS", "MN6": "6MS", "MN24": "24MS"}
TD_PAGE_SIZE = 5000
TD_PAGES = {"D1": 3}
radar_tfs = ["M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1", "MN3"]
RADAR_HTF_MAP = {
    "M15": "H4", "M30": "H4", "H1": "D1", "H2": "D1", "H4": "W1", "H8": "W1",
    "D1": "MN1", "W1": "MN3", "MN1": "MN3", "MN3": "MN3",
}
TERMINAL_HTF_MAP = {**RADAR_HTF_MAP, "M1": "M15", "M5": "H1", "MN6": "MN24", "MN24": "MN24"}
CRYPTO_PREFIXES = ("BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "BCH")
CRYPTO_HTF_OVERRIDE = {"W1": "MN1", "MN1": "MN1", "MN3": "MN1"}
MIN_LTF_BARS = 110
MIN_HTF_BARS = 80
KIHON_SUU = [9, 17, 26, 33, 42, 52, 65, 76, 129, 172, 226, 257]
TIME_AXIS_FORWARD_BARS = 76      # горизонт проекции: +76 баров от точки C (канон Какан)
MN_MONTHS = {"MN1": 1, "MN3": 3, "MN6": 6, "MN24": 24}
KIJUN_ZONE_ATR = 0.3
STOP_BUFFER_ATR = 0.2
LOT_STEP = 0.01
RISK_PCT_DEFAULT = 0.5           # Blue Guardian: дефолт риска на сделку, %
RISK_PCT_STEP = 0.1              # шаг ввода риска, %
USDJPY_APPROX = 155.0
AUDUSD_APPROX = 0.65
MT5_DEFAULT_TOKEN = "SECRET_ICHIMOKU_TOKEN"
MT5_EXEC_MARK = "IG_EXEC"
TRIG_WATCH_BARS = {"hosoda": 3, "break_b": 17}
ATR_CHASE_LIMIT = 1.0
CAND_C_BARS = 3
ACCENT_MUTED = "#a88a45"         # единственный институциональный акцентный тон (matte antique gold)
CAND_C_COLOR = ACCENT_MUTED
CAND_HOVER_BG = "rgba(20, 24, 35, 0.85)"
CAND_HOVER_BORDER = ACCENT_MUTED
CAND_HOVER_FONT = "#E8EDF5"
MINOR_COLOR = "#95a5a6"
MAJOR_COLOR = "#2c3e50"
ORIGIN_COLOR = "#7f8c8d"         # Point O (Origin/Anchor)
WAVE_LABEL_COLOR = "#f39c12"     # подписи A/B/C и полилиния волны
LABEL_BG = "rgba(255, 255, 255, 0.75)"
SURFACE = "#fbfcfd"
BORDER = "#dfe4ea"
BORDER_HOVER = "#2c3e50"
SURFACE_HOVER = "#eef2f5"
SURFACE_ACTIVE = "#e3e9ee"
TELEMETRY_LIVE_SECONDS = 60      # age < 60s -> LIVE, иначе OFFLINE
TELEMETRY_DAILY_CAP = 3.0        # Blue Guardian: daily drawdown hard cap

LANGS = {"English": "en", "Русский": "ru"}
DEFAULT_LANG = "Русский"
LANG = LANGS[DEFAULT_LANG]

I18N = {
    "en": {
        "nav": "Navigation", "module": "Select Module:",
        "mode_radar": "Market Scanner (Radar)", "mode_terminal": "Analytical Terminal",
        "data_settings": "Data Settings (Radar + Terminal)", "server_time": "Server Time (MT5):",
        "raw": "Include Saturday & closing night (raw)",
        "raw_help": "Off: Saturday and closed hours (Fri 17:00 NY - Sun 17:00 NY) are removed, Sunday evening is kept. On: raw provider data with no filtering at all.",
        "clearing": "Drop 23:00 Clearing",
        "clearing_help": "Removes the 23:00 server-time hour (it exists in MT5). Off by default.",
        "terminal_settings": "Terminal Settings", "symbol": "Symbol:", "timeframe": "Timeframe:",
        "wave_points": "Wave Points (A-B-C-O)", "pt_a": "A (Start)", "pt_b": "B (Peak/Trough)", "pt_c": "C (Retracement)", "pt_o": "O (Origin)",
        "awaiting": "Awaiting {label}...", "awaiting_origin": "Awaiting Origin (click 4, optional)",
        "clear_points": "Clear Points",
        "refresh": "↻",
        "refresh_help": "Refresh quotes. Wave A-B-C, price and time targets are preserved.",
        "scanner_title": "Global Market Scanner",
        "filter_active": "Show active signals only (hide 'Waiting')",
        "run_scan_all": "Scan all timeframes", "processing_tf": "Processing {asset} / {tf}...",
        "col_tf": "TF", "sig_wait": "◇ Waiting", "select_tf": "Select Timeframe:",
        "run_scan": "Execute Market Scan", "scanning": "Scanning market data...", "processing": "Processing {asset}...",
        "teleport": "➔ Open {asset} ({tf}) in Analytical Terminal",
        "col_asset": "Asset", "col_signal": "Signal", "col_htf": "HTF Trend", "col_price": "Price",
        "col_kijun": "Kijun", "col_reason": "Reason",
        "diag_distance": "Kijun distance {dist} (threshold {zone}) - {gap} to go",
        "diag_zone": "Zone reached, missing: {fails}",
        "diag_f_kumo": "Kumo", "diag_f_chikou": "Chikou",
        "diag_flat": "Tenkan = Kijun - no direction",
        "trend_up": "▲ UP", "trend_down": "▼ DOWN", "trend_flat": "◆ FLAT",
        "sig_strong_buy": "▲▲ STRONG BUY (HTF Confirmed)", "sig_local_buy": "▲ Local BUY",
        "sig_strong_sell": "▼▼ STRONG SELL (HTF Confirmed)", "sig_local_sell": "▼ Local SELL",
        "no_setups": "Scan completed. No valid entry setups found near Kijun-sen.",
        "skipped": "Skipped assets ({n})",
        "stale_scan": "These results are from an earlier scan (the timeframe or data settings have changed since). Run the scan again to refresh them.",
        "no_data": "Market data is currently unavailable.", "reason": "Reason: {detail}",
        "points_outside": "Some A-B-C points are outside the visible 250 candles - press Clear Points or change the timeframe.",
        "chart_price": "Price", "chart_kumo": "Kumo Cloud",
        "chart_minor_high": "Minor High", "chart_minor_low": "Minor Low",
        "chart_major_high": "Major High", "chart_major_low": "Major Low",
        "chart_minor_group": "Minor fractals", "chart_major_group": "Major fractals",
        "chart_time_targets": "Time targets", "hover_high": "High", "hover_low": "Low",
        "hover_kihon": "Kihon suu {k}", "hover_taiyosuu": "Taiyosuu {name} ({n} bars)", "hover_forecast": "forecast",
        "chart_wave": "Wave A-B-C", "chart_cand_c": "Cand. C", "chart_origin": "Cycle Origin",
        "cand_full": "Preliminary C",
        "cand_hover": "<b>Preliminary C:</b> %{customdata:.5f}<extra></extra>",
        "origin_hover": "<b>Cycle Origin:</b> %{customdata:.5f}<extra></extra>",
        "pts_bar": "Points selected: <b>{n}/3</b>",
        "pts_bar_3_with_origin": "Points: 3/3 (Origin: Point A)",
        "pts_bar_4": "Points: 4/4 (Origin: locked)",
        "pts_hint": "cand. C",
        "pts_reset_tip": "Click/Tap to clear wave points (Reset Points)",
        "pts_hint_tip": "Preliminary C: extremum of the last 3 bars including the live one, for an early entry. Tap the marker to place a wave point before the fractal forms. Toggle layers in the chart legend - one click switches a whole fractal group. Click 4 to set cycle origin.",
        "telemetry_title": "Account Health",
        "telemetry_live": "LIVE",
        "telemetry_offline": "OFFLINE · last seen {m}m ago",
        "telemetry_unavailable": "OFFLINE — telemetry unavailable",
        "telemetry_locked": "Locked: live from MT5 equity",
        "risk_title": "Trade parameters (calculated)", "risk_buy": "BUY", "risk_sell": "SELL",
        "entry_mode": "Entry point",
        "entry_hosoda": "Hosoda: C reversal", "entry_break_b": "Point B breakout",
        "entry_market": "At market", "entry_custom": "Custom entry price",
        "entry_custom_label": "Entry price", "entry_custom_hint": "Enter the exact sniper entry price.",
        "trig_level": "Trigger level", "trig_decision": "Decision",
        "dec_market": "Market now", "dec_limit": "Limit at level", "dec_watch": "Wait for close",
        "dec_expired": "Window expired", "dec_invalid": "Not calculated",
        "trig_window": "Window, bars", "trig_expire": "Valid until",
        "trig_confirm": "Confirmation", "trig_confirm_wait": "pending",
        "trig_dist": "Distance from level",
        "risk_confirm_level": "Confirmation level", "risk_entry_time": "Confirmation bar",
        "risk_wait": "Waiting for confirmation: a bar close {dir} {level} is required.",
        "risk_wait_above": "above", "risk_wait_below": "below",
        "risk_entry": "Entry", "risk_entry_plan": "Entry (planned)",
        "risk_stop_buy": "Stop (C − 0.2 ATR)", "risk_stop_sell": "Stop (C + 0.2 ATR)",
        "risk_stop_cloud_buy": "Stop (Kumo − 0.2 ATR)", "risk_stop_cloud_sell": "Stop (Kumo + 0.2 ATR)",
        "risk_target": "Target N", "risk_risk": "Risk", "risk_reward": "Reward", "risk_rr": "Risk : Reward",
        "trig_no_cloud": "Kumo is not ready yet - the stop for a B breakout cannot be calculated.",
        "trig_ref_missing": "Reference candle not found in history - pick the point again.",
        "trig_expired_note": "Watch window expired ({bars} bars after the reference candle). Pick a fresher point or use At market.",
        "trig_rule_note": "Chase rule: distance from level <= {lim} ATR ({atr}) - market entry; beyond that - a limit order at the level itself. Stop buffer 0.2 ATR = {buf}.",
        "risk_pct_label": "Risk per trade, %",
        "risk_pct_help": "Share of equity lost if the stop is hit. Blue Guardian default 0.5 %, step 0.1 %. The EA applies its own hard cap on top of this.",
        "deposit_label": "Deposit, $",
        "deposit_help": "Account equity in USD used to convert the risk percentage into money risk.",
        "lot_line": "Recommended lot: <b>{lots}</b> (Risk: -{risk} | Target N: +{gain})",
        "lot_too_small": "Calculated size is below 0.01 lot - the EA will reject this order. Reduce the risk distance or increase the deposit.",
        "lot_no_value": "Point value in USD is unavailable for this instrument - lot size cannot be calculated.",
        "risk_outcome": "At {pct}% risk: stop -{loss}% of equity, target +{gain}% of equity. Break-even win rate: {be}%.",
        "risk_units": "Units: Forex - pip 0.0001 (JPY 0.01), others - 1.0 price unit. Point value per 1 lot ~ {pv} USD. ATR used = {atr}.",
        "risk_geom_bad": "Geometry is inverted: the entry is already beyond the stop or the target - distances are shown as absolute values.",
        "risk_zero": "Stop equals the entry price - Risk : Reward and lot size are undefined.",
        "mt5_exec_btn": "➔ Execute order in MetaTrader 5",
        "mt5_need_entry": "Entry is not defined - the order button is locked. Pick a fresher point or another entry mode.",
        "mt5_no_secrets": "Add TELEGRAM_TOKEN and TELEGRAM_CHAT_ID to the app secrets.",
        "mt5_sending": "Sending the order card to Telegram...",
        "mt5_sent": "Order card sent to Telegram. Tap the confirmation button in the chat - the EA acts only after your tap.",
        "mt5_sent_id": "Order {oid} · {sym} {side} · {dec} · {lots} lots · risk {risk}%",
        "mt5_confirm_note": "Telegram never delivers a bot its own messages: without your tap there will be no trade. A second tap on the same card will not open a second position.",
        "mt5_after_watch": "After confirmation the EA arms a watch and enters on a bar close beyond the level.",
        "mt5_after_limit": "After confirmation the EA places a limit order at the level and waits for price to return.",
        "tg_confirm_btn": "✅ Confirm: {sym} {side} {lots} lots",
        "mt5_err": "Gateway error: {detail}",
        "pt_pip": "pips", "pt_point": "pts",
        "err_nodata": "no data", "err_yahoo_nodata": "Yahoo: no data for {detail}",
        "err_td": "TwelveData: {detail}", "err_td_nodata": "TwelveData: no data", "err_exception": "{detail}",
        "err_no_processed": "no data after processing",
        "err_few_bars": "not enough bars (LTF {ltf}/{min_ltf}, HTF {htf}/{min_htf})",
        "err_nan": "indicators not ready (NaN)",
        "err_crypto_hist": "Crypto: not enough {tf} history",
        "crypto_hist_note": "Crypto: only {n} bars available for {tf} - indicators and the AI model may be unavailable.",
        "ai_title": "AI Probability Analysis (Alice Model)",
        "ai_hint": "Select points A, B and C on the chart to run the model.",
        "ai_light_green": "High probability of success", "ai_light_yellow": "Moderate potential",
        "ai_light_red": "Low probability / High risk",
        "ai_details_title": "AI analysis details (for experts)", "ai_target_name": "Target {target}",
        "ai_d_probs": "Outcome probabilities: target {pt}% | stop {ps}% | timeout {p0}%",
        "ai_d_fair": "Fair target probability (target vs stop): {pf}% | Break-even: {be}% (Risk : Reward = 1 : {rr})",
        "ai_d_edge": "Statistical Edge: {edge}% (s.e. +/-{se}%, {neff} distinct waves). Timeouts are excluded; spread and commissions are not included.",
        "ai_det_target": "Target {target} was already crossed at the C bar close: the outcome is known (target reached).",
        "ai_det_stop": "Level C was already broken at the C bar close: the outcome is known (stop).",
        "tg_button": "Send report to Telegram", "tg_sending": "Sending report...", "tg_sent": "Report sent to Telegram.",
        "tg_sent_text": "Chart image is unavailable (install kaleido or matplotlib); a text-only report was sent.",
        "tg_err": "Telegram error: {detail}",
        "tg_no_secrets": "Add TELEGRAM_TOKEN and TELEGRAM_CHAT_ID to the app secrets.",
        "tg_report": "Ichimoku Wave Terminal\n{symbol} | {tf} | {bar}\nPrice: {price}\nHTF trend ({htf}): {trend}\nTarget N: {target}\nAI verdict: {verdict}",
        "tg_up": "Bullish", "tg_down": "Bearish", "tg_flat": "Neutral", "tg_na": "n/a",
        "ai_stats": "Samples: {n} ({neff} distinct waves) | Historical outcomes: target {ft}% / stop {fs}% / timeout {f0}% | Holdout AUC: {auc}",
        "ai_fractals": "Fractals: A - {a}, B - {b}, C - {c}",
        "ai_fr_major": "Major", "ai_fr_minor": "Minor", "ai_fr_pending": "Pending (too recent for Major confirmation)",
        "ai_setup": "Zero-lag inference: entry on bar C (lag {lag}) | Horizon, bars: {h} (A-C time, min {hmin}) | Class B {ab} / C {cls}",
        "ai_cls_major": "major", "ai_cls_minor": "minor",
        "ai_pooled": "Too few waves of this exact class: the model was trained on waves of all fractal classes (scale-free distances).",
        "ai_live": "Point C is recent: its fractal class is not final yet, so the model was trained in real-time mode.",
        "ai_freq_only": "Too few rare outcomes to train a model ({k} of {n} similar waves reached the target, or nearly all did); showing the historical frequency.",
        "ai_na": "n/a",
        "ai_uplift": "Ichimoku-feature uplift (AUC vs wave-geometry-only model): {v}",
        "ai_rel_high": "Model confidence: high", "ai_rel_mod": "Model confidence: moderate",
        "ai_rel_low": "Model confidence: low - the estimate mostly reflects wave geometry, Ichimoku features add little",
        "ai_disclaimer": "Statistical estimate from this instrument's own history, zero-lag: features use bars up to C only. Not a trading signal.",
        "ai_htf_missing": "Higher-timeframe trend is unavailable; a neutral value was used.",
        "ai_err_sklearn": "scikit-learn is not installed. Add it to requirements.txt.",
        "ai_err_fresh": "Point C is outside the loaded history.",
        "ai_err_geom": "Invalid wave geometry: point C must lie between A and B.",
        "ai_err_nan": "Indicators are not ready at point C (not enough history).",
        "ai_err_samples": "Not enough comparable historical waves ({n} found, at least {min} required).",
        "history_partial": "Part of the history could not be loaded ({detail}); the chart may be shorter than usual.",
    },
    "ru": {
        "nav": "Навигация", "module": "Выберите модуль:",
        "mode_radar": "Сканер рынка (Радар)", "mode_terminal": "Аналитический терминал",
        "data_settings": "Настройки данных (Радар + Терминал)", "server_time": "Серверное время (MT5):",
        "raw": "Считать субботу и ночь закрытия (сырые данные)",
        "raw_help": "Выкл: суббота и закрытые часы (пт 17:00 NY — вс 17:00 NY) убраны, воскресный вечер остаётся. Вкл: сырые данные провайдера без какой-либо фильтрации.",
        "clearing": "Убрать клиринг 23:00",
        "clearing_help": "Вырезает час 23:00 серверного времени (в MT5 этот час есть). По умолчанию выключено.",
        "terminal_settings": "Настройки терминала", "symbol": "Инструмент:", "timeframe": "Таймфрейм:",
        "wave_points": "Точки волны (A-B-C-O)", "pt_a": "A (начало)", "pt_b": "B (пик/впадина)", "pt_c": "C (откат)", "pt_o": "O (Исток)",
        "awaiting": "Ожидается {label}...", "awaiting_origin": "Ожидается Исток (клик 4, опционально)",
        "clear_points": "Сбросить точки",
        "refresh": "↻",
        "refresh_help": "Обновить котировки. Волна A-B-C, цели по цене и по времени сохраняются.",
        "scanner_title": "Глобальный сканер рынка",
        "filter_active": "Показывать только активные сигналы (Скрыть 'Ждем')",
        "run_scan_all": "Сканировать все таймфреймы", "processing_tf": "Обработка: {asset} / {tf}...",
        "col_tf": "ТФ", "sig_wait": "◇ Ждем", "select_tf": "Выберите таймфрейм:",
        "run_scan": "Запустить сканирование", "scanning": "Сканирование рынка...", "processing": "Обработка: {asset}...",
        "teleport": "➔ Открыть {asset} ({tf}) в Аналитическом терминале",
        "col_asset": "Актив", "col_signal": "Сигнал", "col_htf": "Старший тренд", "col_price": "Цена",
        "col_kijun": "Киджун", "col_reason": "Причина",
        "diag_distance": "До Киджун {dist} (порог {zone}) — ждём ещё {gap}",
        "diag_zone": "Зона есть, нет подтверждения: {fails}",
        "diag_f_kumo": "Облако", "diag_f_chikou": "Чикоу",
        "diag_flat": "Тенкан = Киджун — направление не определено",
        "trend_up": "▲ ВВЕРХ", "trend_down": "▼ ВНИЗ", "trend_flat": "◆ ФЛЭТ",
        "sig_strong_buy": "▲▲ СИЛЬНАЯ ПОКУПКА (старший ТФ подтверждает)", "sig_local_buy": "▲ Локальная ПОКУПКА",
        "sig_strong_sell": "▼▼ СИЛЬНАЯ ПРОДАЖА (старший ТФ подтверждает)", "sig_local_sell": "▼ Локальная ПРОДАЖА",
        "no_setups": "Сканирование завершено. Подходящих точек входа у Киджун-сен не найдено.",
        "skipped": "Пропущенные активы ({n})",
        "stale_scan": "Эти результаты получены в предыдущем сканировании (с тех пор изменились таймфрейм или настройки данных). Запустите сканирование заново, чтобы обновить их.",
        "no_data": "Рыночные данные сейчас недоступны.", "reason": "Причина: {detail}",
        "points_outside": "Часть точек A-B-C вышла за пределы видимых 250 свечей — нажмите «Сбросить точки» или смените таймфрейм.",
        "chart_price": "Цена", "chart_kumo": "Облако Кумо",
        "chart_minor_high": "Малый максимум", "chart_minor_low": "Малый минимум",
        "chart_major_high": "Главный максимум", "chart_major_low": "Главный минимум",
        "chart_minor_group": "Малые фракталы", "chart_major_group": "Главные фракталы",
        "chart_time_targets": "Временные цели", "hover_high": "Хай", "hover_low": "Лоу",
        "hover_kihon": "Kihon suu {k}", "hover_taiyosuu": "Taiyosuu {name} ({n} баров)", "hover_forecast": "прогноз",
        "chart_wave": "Волна A-B-C", "chart_cand_c": "Предв. C", "chart_origin": "Исток цикла",
        "cand_full": "Предварительная C",
        "cand_hover": "<b>Предварительная C:</b> %{customdata:.5f}<extra></extra>",
        "origin_hover": "<b>Исток цикла:</b> %{customdata:.5f}<extra></extra>",
        "pts_bar": "Выбрано точек: <b>{n}/3</b>",
        "pts_bar_3_with_origin": "Выбрано точек: 3/3 (Исток: точка A)",
        "pts_bar_4": "Выбрано точек: 4/4 (Исток: зафиксирован)",
        "pts_hint": "предв. C",
        "pts_reset_tip": "Нажмите, чтобы сбросить точки (Reset Points)",
        "pts_hint_tip": "Предварительный экстремум точки C по последним 3 барам, включая текущий, для раннего входа. Нажмите маркер, чтобы поставить точку волны до формирования фрактала. Слои переключаются в легенде: один клик гасит всю группу фракталов. Клик 4 — исток цикла.",
        "telemetry_title": "Здоровье счёта",
        "telemetry_live": "LIVE",
        "telemetry_offline": "OFFLINE · последний сигнал {m} мин назад",
        "telemetry_unavailable": "OFFLINE — телеметрия недоступна",
        "telemetry_locked": "Синхронизировано с эквити MT5",
        "risk_title": "Параметры сделки (расчет)", "risk_buy": "ПОКУПКА", "risk_sell": "ПРОДАЖА",
        "entry_mode": "Точка входа",
        "entry_hosoda": "Хосода: разворот C", "entry_break_b": "Пробой точки B",
        "entry_market": "По текущей цене", "entry_custom": "Своя цена входа",
        "entry_custom_label": "Цена входа", "entry_custom_hint": "Введите точную цену снайперского входа.",
        "trig_level": "Уровень пробоя", "trig_decision": "Решение",
        "dec_market": "Рынок сейчас", "dec_limit": "Лимит на уровень", "dec_watch": "Ждём закрытия",
        "dec_expired": "Окно истекло", "dec_invalid": "Не рассчитано",
        "trig_window": "Окно, свечей", "trig_expire": "Действует до",
        "trig_confirm": "Подтверждение", "trig_confirm_wait": "ожидается",
        "trig_dist": "Уход от уровня",
        "risk_confirm_level": "Уровень подтверждения", "risk_entry_time": "Бар подтверждения",
        "risk_wait": "Ожидание подтверждения: нужно закрытие свечи {dir} {level}.",
        "risk_wait_above": "выше", "risk_wait_below": "ниже",
        "risk_entry": "Вход", "risk_entry_plan": "Вход (ориентир)",
        "risk_stop_buy": "Стоп (C − 0.2·ATR)", "risk_stop_sell": "Стоп (C + 0.2·ATR)",
        "risk_stop_cloud_buy": "Стоп (Облако − 0.2·ATR)", "risk_stop_cloud_sell": "Стоп (Облако + 0.2·ATR)",
        "risk_target": "Цель N", "risk_risk": "Риск", "risk_reward": "Прибыль", "risk_rr": "Риск : Прибыль",
        "trig_no_cloud": "Облако ещё не готово — стоп для пробоя B рассчитать нельзя.",
        "trig_ref_missing": "Опорная свеча не найдена в истории — выберите точку заново.",
        "trig_expired_note": "Окно наблюдения истекло ({bars} свечей после опорной свечи). Возьмите более свежую точку или режим «По текущей цене».",
        "trig_rule_note": "Правило догона: уход от уровня ≤ {lim}·ATR ({atr}) — вход по рынку; дальше — лимитный ордер на самый уровень. Буфер стопа 0.2·ATR = {buf}.",
        "risk_pct_label": "Риск на сделку, %",
        "risk_pct_help": "Доля депозита, теряемая при срабатывании стопа. Дефолт Blue Guardian 0.5 %, шаг 0.1 %. Советник дополнительно применит свой жесткий потолок риска.",
        "deposit_label": "Депозит, $",
        "deposit_help": "Размер счета в USD для перевода процента риска в денежный риск. При LIVE телеметрии — автоподстановка эквити MT5.",
        "lot_line": "Рекомендуемый лот: <b>{lots}</b> (Риск: −{risk} | Цель N: +{gain})",
        "lot_too_small": "Расчетный объем меньше 0.01 лота — советник отклонит приказ. Уменьшите дистанцию риска или увеличьте депозит.",
        "lot_no_value": "Стоимость пункта в USD для этого инструмента недоступна — лот рассчитать нельзя.",
        "risk_outcome": "При риске {pct}%: стоп −{loss}% депозита, цель +{gain}% депозита. Безубыточная доля прибыльных: {be}%.",
        "risk_units": "Пункты: Форекс — пипс 0.0001 (JPY 0.01), прочие — 1.0 ед. цены. Стоимость пункта на 1 лот ≈ {pv} USD. Использованный ATR = {atr}.",
        "risk_geom_bad": "Геометрия вывернута: вход уже за стопом или за целью — дистанции показаны по модулю.",
        "risk_zero": "Стоп совпадает с ценой входа — соотношение R:R и объем не определены.",
        "mt5_exec_btn": "➔ Исполнить приказ в MetaTrader 5",
        "mt5_need_entry": "Вход не определён — кнопка приказа заблокирована. Возьмите более свежую точку или другой режим входа.",
        "mt5_no_secrets": "Добавьте TELEGRAM_TOKEN и TELEGRAM_CHAT_ID в секреты приложения.",
        "mt5_sending": "Передача карточки приказа в Telegram...",
        "mt5_sent": "Карточка приказа отправлена в Telegram. Нажмите кнопку подтверждения в чате — советник действует только после вашего нажатия.",
        "mt5_sent_id": "Приказ {oid} · {sym} {side} · {dec} · {lots} лота · риск {risk}%",
        "mt5_confirm_note": "Telegram не доставляет боту его собственные сообщения: без вашего нажатия сделки не будет. Повторное нажатие той же карточки не откроет вторую позицию.",
        "mt5_after_watch": "После подтверждения советник взведёт наблюдение и войдёт по закрытию свечи за уровнем.",
        "mt5_after_limit": "После подтверждения советник выставит лимитный ордер на уровень и будет ждать возврата цены.",
        "tg_confirm_btn": "✅ Подтвердить: {sym} {side} {lots} лота",
        "mt5_err": "Ошибка шлюза: {detail}",
        "pt_pip": "пипс", "pt_point": "п.",
        "err_nodata": "нет данных", "err_yahoo_nodata": "Yahoo: нет данных для {detail}",
        "err_td": "TwelveData: {detail}", "err_td_nodata": "TwelveData: нет данных", "err_exception": "{detail}",
        "err_no_processed": "нет данных после обработки",
        "err_few_bars": "мало баров (LTF {ltf}/{min_ltf}, HTF {htf}/{min_htf})",
        "err_nan": "индикаторы не готовы (NaN)",
        "err_crypto_hist": "Крипта: истории для {tf} недостаточно",
        "crypto_hist_note": "Крипта: для {tf} доступно только {n} свечей — индикаторы и ИИ-модель могут быть недоступны.",
        "ai_title": "ИИ-анализ вероятности (модель Alice)",
        "ai_hint": "Выберите на графике точки A, B и C, чтобы запустить модель.",
        "ai_light_green": "Высокая вероятность успеха", "ai_light_yellow": "Средний потенциал",
        "ai_light_red": "Низкая вероятность / Опасно",
        "ai_details_title": "Подробности ИИ-анализа (для экспертов)", "ai_target_name": "Цель {target}",
        "ai_d_probs": "Вероятности исходов: цель {pt}% | стоп {ps}% | таймаут {p0}%",
        "ai_d_fair": "Честная вероятность цели (цель против стопа): {pf}% | Безубыточная: {be}% (риск : прибыль = 1 : {rr})",
        "ai_d_edge": "Statistical Edge: {edge}% (s.e. +/-{se}%, {neff} различных волн). Таймауты исключены; спред и комиссии не учтены.",
        "ai_det_target": "Цель {target} уже пересечена на закрытии бара C: исход известен (цель достигнута).",
        "ai_det_stop": "Уровень C уже пробит на закрытии бара C: исход известен (стоп).",
        "tg_button": "Отправить отчет в Telegram", "tg_sending": "Отправка отчета...", "tg_sent": "Отчет отправлен в Telegram.",
        "tg_sent_text": "Изображение графика недоступно (установите kaleido или matplotlib); отправлен только текстовый отчет.",
        "tg_err": "Ошибка Telegram: {detail}",
        "tg_no_secrets": "Добавьте TELEGRAM_TOKEN и TELEGRAM_CHAT_ID в секреты приложения.",
        "tg_report": "Ichimoku Wave Terminal\n{symbol} | {tf} | {bar}\nЦена: {price}\nТренд HTF ({htf}): {trend}\nЦель N: {target}\nВердикт ИИ: {verdict}",
        "tg_up": "Бычий", "tg_down": "Медвежий", "tg_flat": "Нейтральный", "tg_na": "н/д",
        "ai_stats": "Выборка: {n} ({neff} различных волн) | Исторические исходы: цель {ft}% / стоп {fs}% / таймаут {f0}% | AUC на отложенной выборке: {auc}",
        "ai_fractals": "Фракталы: A — {a}, B — {b}, C — {c}",
        "ai_fr_major": "Главный", "ai_fr_minor": "Малый", "ai_fr_pending": "Pending (слишком свежая точка для подтверждения Major)",
        "ai_setup": "Zero-lag: вход на баре C (лаг {lag}) | Горизонт, баров: {h} (время A-C, минимум {hmin}) | Класс B {ab} / C {cls}",
        "ai_cls_major": "главный", "ai_cls_minor": "малый",
        "ai_pooled": "Волн именно этого класса слишком мало: модель обучена на волнах всех классов фракталов (безразмерные дистанции).",
        "ai_live": "Точка C свежая: её класс фрактала ещё не окончателен, поэтому модель обучена в режиме реального времени.",
        "ai_freq_only": "Редких исходов слишком мало для обучения модели ({k} из {n} похожих волн дошли до цели, либо почти все); показана историческая частота.",
        "ai_na": "н/д",
        "ai_uplift": "Вклад признаков Ишимоку (AUC против модели только по геометрии волны): {v}",
        "ai_rel_high": "Уверенность модели: высокая", "ai_rel_mod": "Уверенность модели: умеренная",
        "ai_rel_low": "Уверенность модели: низкая — оценка в основном отражает геометрию волны, признаки Ишимоку добавляют мало",
        "ai_disclaimer": "Статистическая оценка по собственной истории инструмента, zero-lag: признаки только по барам до C включительно. Не торговый сигнал.",
        "ai_htf_missing": "Тренд старшего таймфрейма недоступен, использовано нейтральное значение.",
        "ai_err_sklearn": "Библиотека scikit-learn не установлена. Добавьте её в requirements.txt.",
        "ai_err_fresh": "Точка C вне загруженной истории.",
        "ai_err_geom": "Некорректная геометрия волны: точка C должна лежать между A и B.",
        "ai_err_nan": "На точке C индикаторы ещё не готовы (мало истории).",
        "ai_err_samples": "Недостаточно похожих исторических волн (найдено {n}, нужно минимум {min}).",
        "history_partial": "Часть истории не загрузилась ({detail}); график может быть короче обычного.",
    },
}


def asset_label(name):
    return ASSET_LABELS_EN.get(name, name) if LANG == "en" else name


def t(key, **kw):
    text = I18N.get(LANG, {}).get(key) or I18N["en"].get(key, key)
    return text.format(**kw) if kw else text


def cand_trace_name():
    """Единый токен слоя Preliminary C: регистрация трейса и детекция клика. Без глифов."""
    return t("chart_cand_c")


def polar_anchor(df_plot, px, py):
    """Динамическая полярность подписи точки волны.
    Возвращает (y_anchor, yshift_plotly, yanchor_plotly, y_offset_mpl, va_mpl):
    точка у High свечи -> якорь над верхней тенью; у Low -> под нижней тенью."""
    row = df_plot.iloc[int(px)]
    hi, lo = float(row["High"]), float(row["Low"])
    if abs(py - hi) <= abs(py - lo):
        return hi, 14, "bottom", 8, "bottom"
    return lo, -14, "top", -12, "top"


def E(code, **kw):
    return (code, kw)


def fmt_err(err):
    if isinstance(err, tuple):
        return t("err_" + err[0], **err[1])
    return str(err)


def _secret_values():
    vals = [API_KEY]
    for k in ("TELEGRAM_TOKEN", "MT5_SECRET_TOKEN", "SUPABASE_KEY"):
        try:
            v = st.secrets.get(k, "")
            if v:
                vals.append(str(v))
        except Exception:
            pass
    return [v for v in vals if v and len(v) >= 6]


def safe_err(e):
    txt = e if isinstance(e, str) else f"{type(e).__name__}: {e}"
    for s in _secret_values():
        txt = txt.replace(s, "***")
    return txt


def mt5_symbol(asset_key):
    base = re.sub(r"\(.*?\)", "", asset_key)
    base = re.sub(r"[\s/]+", "", base).strip().upper()
    if not base or not base.isascii():
        route = ASSET_ROUTER.get(asset_key)
        src = route["sym"] if route else asset_key
        base = re.sub(r"[\s/]+", "", src).upper()
    return base


def price_digits(price):
    if price >= 1000:
        return 2
    if price >= 10:
        return 3
    return 5


def fmt_dist(v):
    if v >= 100:
        return f"{v:.1f}"
    if v >= 1:
        return f"{v:.2f}"
    return f"{v:.5f}"


def fmt_diag(d):
    if not d:
        return ""
    kind, kw = d
    if kind == "distance":
        return t("diag_distance", dist=fmt_dist(kw["dist"]), zone=fmt_dist(kw["zone"]), gap=fmt_dist(kw["gap"]))
    if kind == "zone":
        return t("diag_zone", fails=", ".join(t("diag_f_" + f) for f in kw["fails"]))
    return t("diag_" + kind)


def point_size(route):
    sym = route["sym"]
    if "/" in sym and "BTC" not in sym and "XAU" not in sym:
        return (0.01, "pt_pip") if sym.endswith("JPY") else (0.0001, "pt_pip")
    return (1.0, "pt_point")


def _fx_last(sym_yf):
    try:
        dfx, errx = fetch_yahoo(sym_yf, "M15")
        if errx or dfx.empty:
            return None
        v = float(dfx["Close"].iloc[-1])
        return v if v > 0.0 else None
    except Exception:
        return None


def pip_value_usd(asset_key, current_price, psize):
    """Стоимость 1 пункта/пипса в USD на 1 стандартный лот."""
    route = ASSET_ROUTER.get(asset_key)
    sym = route["sym"] if route else asset_key
    if "BTC" in sym:
        return 1.0 * psize
    if "XAU" in sym:
        return 100.0 * psize
    if "/" not in sym:
        return 1.0 * psize
    amount = 100000.0 * psize
    quote = sym.split("/")[1]
    if quote == "USD":
        return amount
    if quote == "JPY":
        if "USD/JPY" in sym and current_price > 0.0:
            rate = current_price
        else:
            rate = _fx_last("USDJPY=X") or USDJPY_APPROX
        return amount / rate if rate > 0.0 else amount / USDJPY_APPROX
    if quote == "AUD":
        rate = _fx_last("AUDUSD=X") or AUDUSD_APPROX
        return amount * rate
    rate = _fx_last(f"{quote}USD=X")
    return amount * rate if rate else amount


def fmt_money(v, ccy):
    s = f"{v:,.2f}".replace(",", " ")
    return f"{s} {ccy}" if ccy else s


def fmt_points(v, size):
    p = v / size
    s = f"{p:,.1f}" if size < 1 else f"{p:,.2f}"
    return s.replace(",", " ")


def risk_card_html(head, rows, accent):
    body = "".join(f"<tr><td class='rl'>{k}</td><td class='rv'>{v}</td></tr>" for k, v in rows)
    return (f"<div class='risk-card' style='border-left-color:{accent}'>"
            f"<div class='risk-hd'>{head}</div><table class='risk-tb'>{body}</table></div>")


def points_bar_text(n):
    """Чистая текстовая метка интерактивной статус-пилюли (без HTML).
    Сохраняет композицию прежней полосы: статус слева, подсказка слоя справа."""
    if n < 3:
        status = t("pts_bar", n=int(n))
    elif n == 3:
        status = t("pts_bar_3_with_origin")
    else:
        status = t("pts_bar_4")
    status = re.sub(r"<[^>]+>", "", status)
    return f"{status}  ·  {t('pts_hint')}"


def detect_default_lang():
    try:
        al = st.context.headers.get("Accept-Language", "").lower()
        return "Русский" if "ru" in al else "English"
    except Exception:
        return DEFAULT_LANG


def detect_mobile_ua():
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:
        return False
    if re.search(r"iPad|Tablet|PlayBook|Silk|Kindle", ua, re.I):
        return False
    return bool(re.search(r"Android|iPhone|iPod|Windows Phone|IEMobile|Mobile Safari", ua, re.I))


def chart_ui(mobile):
    if mobile:
        return dict(height=560, margin=dict(l=8, r=58, t=48, b=64), tick_div=5, tick_angle=0,
                    tick_font=dict(size=9), y_font=dict(size=9),
                    legend=dict(orientation="h", yanchor="top", y=-0.20, xanchor="center", x=0.5,
                                font=dict(size=8), groupclick="togglegroup"),
                    ann_font=8, vlabel_font=8, mark_minor=4, mark_major=8, wave_mark=7)
    return dict(height=750, margin=dict(l=20, r=110, t=40, b=120), tick_div=10, tick_angle=45,
                tick_font=None, y_font=None,
                legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5,
                            groupclick="togglegroup"),
                ann_font=10, vlabel_font=9, mark_minor=5, mark_major=10, wave_mark=8)


def candidate_c_extreme(df_plot, bars=CAND_C_BARS):
    """Preliminary C: экстремум до формирования фрактала (живой маркер)."""
    n = len(df_plot)
    if n < 2:
        return None
    lb = max(1, min(int(bars), n))
    win = df_plot.iloc[n - lb:]
    ref = df_plot.iloc[-2]
    tk, kj = float(ref["tenkan"]), float(ref["kijun"])
    if np.isfinite(tk) and np.isfinite(kj) and tk != kj:
        down = tk < kj
    elif np.isfinite(kj):
        down = float(ref["Close"]) < kj
    else:
        down = True

    if down:
        pos = int(np.argmax(win["High"].to_numpy(dtype=float)))
        px = float(win["High"].iloc[pos])
        kind = "high"
    else:
        pos = int(np.argmin(win["Low"].to_numpy(dtype=float)))
        px = float(win["Low"].iloc[pos])
        kind = "low"

    row = win.iloc[pos]
    atr = float(row["ATR"])
    if not np.isfinite(atr) or atr <= 0.0:
        atr = float((win["High"] - win["Low"]).mean())
    if not np.isfinite(atr) or atr <= 0.0:
        atr = abs(px) * 0.0005
    y = px + STOP_BUFFER_ATR * atr if kind == "high" else px - STOP_BUFFER_ATR * atr
    x = n - lb + pos
    return {"x": x, "price": px, "y": y, "kind": kind, "down": down,
            "t": df_plot.index[x], "bars": lb}


def enforce_visible_extremes(df_plot):
    """Абсолютные High/Low видимого окна всегда получают маркер главного фрактала.
    Тай-брейк, плоская вершина или край окна (NaN в shift(-1/-2)) не должны прятать
    доминантный экстремум свинга. Первое вхождение берётся по idxmax / idxmin."""
    mh = df_plot["Major_High"].to_numpy(dtype=bool).copy()
    ml = df_plot["Major_Low"].to_numpy(dtype=bool).copy()
    if len(df_plot) == 0:
        return mh, ml
    try:
        hi_pos = int(df_plot.index.get_loc(df_plot["High"].idxmax()))
        lo_pos = int(df_plot.index.get_loc(df_plot["Low"].idxmin()))
    except Exception:
        hi_pos = int(np.argmax(df_plot["High"].to_numpy(dtype=float)))
        lo_pos = int(np.argmin(df_plot["Low"].to_numpy(dtype=float)))
    mh[hi_pos] = True
    ml[lo_pos] = True
    return mh, ml


def inject_css(mobile):
    mobile_rules = (
        ".block-container { padding-top: 3.2rem !important; padding-left: 0.6rem !important; "
        "padding-right: 0.6rem !important; padding-bottom: 3.4rem !important; }\n"
        "h1, h2, h3 { margin-top: 0.2rem !important; line-height: 1.25 !important; overflow-wrap: anywhere; }\n"
        "h2 { font-size: clamp(1.05rem, 4.5vw, 1.75rem) !important; }\n"
        ".modebar-btn { padding: 3px 5px !important; }\n"
        ".risk-tb td { font-size: 0.8rem; }\n"
        ".lot-line { font-size: 0.88rem; }\n"
        ".st-key-pts_bar_btn { position: fixed; left: 0.6rem; right: 0.6rem; bottom: 0.4rem; "
        "z-index: 60; margin: 0 !important; pointer-events: auto !important; }\n"
        f".st-key-pts_bar_btn button {{ background: rgba(251,252,253,0.97); "
        "box-shadow: 0 -1px 6px rgba(44,62,80,0.10); pointer-events: auto !important; }\n"
        ".st-key-chart_shell .st-key-refresh_term { top: 5px; left: 2px; }\n"
        '[data-testid="stElementToolbar"] { opacity: 1 !important; visibility: visible !important; }\n'
    )
    tool_css = (
        ".st-key-chart_shell { position: relative; }\n"
        ".st-key-refresh_term { display: flex; justify-content: flex-end; margin: 0 0 0.25rem 0; }\n"
        ".st-key-refresh_term button { height: 28px; width: 30px; min-height: 0 !important; "
        "display: inline-flex; align-items: center; justify-content: center; "
        "padding: 0 !important; margin: 0; border: 1px solid #dfe4ea; border-radius: 2px; "
        "background: rgba(255,255,255,0.92); color: #2c3e50; box-shadow: none; "
        "transition: background-color .15s ease, border-color .15s ease; }\n"
        ".st-key-refresh_term button p, .st-key-refresh_term button span { "
        "font-size: 15px !important; line-height: 1 !important; margin: 0 !important; color: #2c3e50; "
        'font-family: "Segoe UI Symbol", "Apple Symbols", "Noto Sans Symbols 2", "DejaVu Sans", sans-serif; }\n'
        ".st-key-refresh_term button:hover { background: #eef2f5; border-color: #2c3e50; color: #2c3e50; }\n"
        ".st-key-refresh_term button:active { background: #e3e9ee; border-color: #2c3e50; }\n"
        ".st-key-refresh_term button:focus-visible { outline: 1px solid #2c3e50; outline-offset: 1px; }\n"
        ".st-key-chart_shell .st-key-refresh_term { position: absolute; top: 6px; left: 4px; "
        "z-index: 7; display: block; width: 30px; height: 28px; "
        "margin: 0 !important; padding: 0 !important; pointer-events: none; }\n"
        ".st-key-chart_shell .st-key-refresh_term button { pointer-events: auto; }\n"
    )
    # Интерактивная статус-пилюля: геометрия и типографика прежней статичной полосы.
    status_css = (
        ".st-key-pts_bar_btn { margin: 2px 0 4px 0; }\n"
        ".st-key-pts_bar_btn button { width: 100%; height: 28px; min-height: 28px !important; "
        f"padding: 0 10px !important; background: {SURFACE}; color: {MAJOR_COLOR}; "
        f"border: 1px solid {BORDER}; border-radius: 2px; box-shadow: none; "
        "display: inline-flex; align-items: center; justify-content: center; "
        "font-weight: 500; letter-spacing: 0.01em; "
        "transition: background-color .15s ease, border-color .15s ease; }\n"
        ".st-key-pts_bar_btn button p, .st-key-pts_bar_btn button span { "
        f"font-size: 0.8rem !important; color: {MAJOR_COLOR} !important; margin: 0 !important; "
        "line-height: 1 !important; font-variant-numeric: tabular-nums; "
        "white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n"
        f".st-key-pts_bar_btn button:hover {{ background: {SURFACE_HOVER}; border-color: {BORDER_HOVER}; }}\n"
        f".st-key-pts_bar_btn button:active {{ background: {SURFACE_ACTIVE}; border-color: {BORDER_HOVER}; }}\n"
        f".st-key-pts_bar_btn button:focus-visible {{ outline: 1px solid {BORDER_HOVER}; outline-offset: 1px; }}\n"
    )
    teleport_css = (
        ".st-key-teleport_btn { margin: 0.4rem 0 0.2rem 0; }\n"
        ".st-key-teleport_btn button { width: 100%; min-height: 44px; padding: 0.5rem 1rem !important; "
        "background: #2c3e50; color: #ffffff; border: 1px solid #2c3e50; border-radius: 2px; "
        "font-weight: 600; letter-spacing: 0.01em; box-shadow: none; "
        "transition: background-color .15s ease, border-color .15s ease; }\n"
        ".st-key-teleport_btn button p, .st-key-teleport_btn button span { "
        "color: #ffffff !important; font-size: 0.95rem !important; line-height: 1.3 !important; }\n"
        ".st-key-teleport_btn button:hover { background: #34495e; border-color: #34495e; color: #ffffff; }\n"
        ".st-key-teleport_btn button:active { background: #22303d; border-color: #22303d; color: #ffffff; }\n"
        ".st-key-teleport_btn button:focus-visible { outline: 2px solid #2980b9; outline-offset: 2px; }\n"
    )
    exec_css = (
        ".st-key-mt5_send_order { margin: 0.4rem 0 0.2rem 0; }\n"
        ".st-key-mt5_send_order button { width: 100%; min-height: 44px; padding: 0.5rem 1rem !important; "
        "background: #2c3e50; color: #ffffff; border: 1px solid #1b2a38; border-radius: 2px; "
        "font-weight: 600; letter-spacing: 0.01em; box-shadow: none; "
        "transition: background-color .15s ease, border-color .15s ease; }\n"
        ".st-key-mt5_send_order button p, .st-key-mt5_send_order button span { "
        "color: #ffffff !important; font-size: 0.95rem !important; line-height: 1.3 !important; }\n"
        ".st-key-mt5_send_order button:hover { background: #34495e; border-color: #1b2a38; color: #ffffff; }\n"
        ".st-key-mt5_send_order button:active { background: #22303d; border-color: #1b2a38; color: #ffffff; }\n"
        ".st-key-mt5_send_order button:focus-visible { outline: 2px solid #2980b9; outline-offset: 2px; }\n"
        ".st-key-mt5_send_order button:disabled { background: #eef1f4; border-color: #dfe4ea; "
        "color: #9aa7b2; cursor: not-allowed; }\n"
        ".st-key-mt5_send_order button:disabled p, .st-key-mt5_send_order button:disabled span { "
        "color: #9aa7b2 !important; }\n"
    )
    risk_css = (
        ".risk-card { border: 1px solid #dfe4ea; border-left: 3px solid #2c3e50; background: #fbfcfd; "
        "padding: 8px 12px; margin: 0.2rem 0 0.5rem 0; border-radius: 2px; }\n"
        ".risk-hd { font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; "
        "color: #7f8c8d; margin-bottom: 4px; }\n"
        ".risk-tb { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }\n"
        ".risk-tb td { padding: 2px 0; font-size: 0.86rem; border-bottom: 1px solid #eef1f4; }\n"
        ".risk-tb tr:last-child td { border-bottom: none; }\n"
        ".risk-tb td.rl { color: #7f8c8d; white-space: nowrap; padding-right: 10px; }\n"
        ".risk-tb td.rv { color: #2c3e50; text-align: right; font-weight: 600; }\n"
        ".lot-line { border-top: 1px solid #dfe4ea; margin: 2px 0 4px 0; padding-top: 6px; "
        "font-size: 0.95rem; color: #2c3e50; font-variant-numeric: tabular-nums; }\n"
        ".lot-line b { font-size: 1.08rem; letter-spacing: 0.01em; }\n"
    )
    telemetry_css = (
        ".telemetry-hud { background: #fbfcfd; border: 1px solid #dfe4ea; border-radius: 2px; "
        "padding: 8px 12px; margin: 0 0 0.5rem 0; font-size: 0.82rem; "
        "font-variant-numeric: tabular-nums; }\n"
        ".telemetry-hud .th-title { font-size: 0.70rem; letter-spacing: 0.08em; "
        "text-transform: uppercase; color: #7f8c8d; margin-bottom: 6px; "
        "display: flex; align-items: center; gap: 6px; }\n"
        ".telemetry-hud .th-dot { width: 8px; height: 8px; border-radius: 50%; "
        "display: inline-block; flex-shrink: 0; }\n"
        ".telemetry-live .th-dot { background: #3f7d5c; animation: th-pulse 1.4s infinite ease-in-out; }\n"
        ".telemetry-offline .th-dot { background: #95a5a6; }\n"
        "@keyframes th-pulse { 0%, 100% { opacity: 1; transform: scale(1); } "
        "50% { opacity: 0.55; transform: scale(1.25); } }\n"
        ".telemetry-hud .th-row { display: grid; grid-template-columns: auto 1fr; "
        "gap: 2px 10px; line-height: 1.55; }\n"
        ".telemetry-hud .th-k { color: #7f8c8d; white-space: nowrap; }\n"
        ".telemetry-hud .th-v { color: #2c3e50; text-align: right; font-weight: 600; }\n"
        ".telemetry-hud .th-foot { margin-top: 4px; font-size: 0.70rem; color: #95a5a6; }\n"
    )
    css = (
        "<style>\n"
        ".block-container { padding-top: 4rem; padding-bottom: 2rem; max-width: 100%; }\n"
        ".app-title { color: #2c3e50; font-size: clamp(1.05rem, 4.5vw, 1.75rem); line-height: 1.25; "
        "margin-top: 0.2rem; overflow-wrap: anywhere; white-space: normal; }\n"
        ".stPlotlyChart .modebar { opacity: 1; }\n"
        + tool_css + status_css + teleport_css + exec_css + risk_css + telemetry_css +
        "@media (max-width: 768px) {\n" + mobile_rules + "}\n"
        "@media (hover: none) {\n"
        ".stPlotlyChart .modebar { opacity: 1 !important; }\n"
        '[data-testid="stElementToolbar"] { opacity: 1 !important; visibility: visible !important; }\n'
        "}\n"
        + (mobile_rules if mobile else "")
        + "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)


def align_start(df, rule):
    if df.empty:
        return df
    if rule == "3MS":
        ok = np.asarray(df.index.month.isin([1, 4, 7, 10]))
    elif rule == "6MS":
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
    if df_utc.empty:
        return df_utc
    ny = df_utc.index.tz_convert("America/New_York")
    dow = np.asarray(ny.dayofweek)
    hour = np.asarray(ny.hour)
    closed = (dow == 5) | ((dow == 4) & (hour >= 17)) | ((dow == 6) & (hour < 17))
    return df_utc.iloc[np.flatnonzero(~closed)]


def glue_sunday(df):
    if df.empty:
        return df
    df = df.sort_index()
    shift = pd.to_timedelta((np.asarray(df.index.dayofweek) == 6).astype(int), unit="D")
    out = df.copy()
    out.index = df.index + shift
    return out.groupby(level=0).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})


SERVER_CHOICES = ["Auto (EET)", "NY close (UTC+2/+3)", "UTC+2", "UTC+3", "UTC"]


def to_server_time(df_utc, choice):
    out = df_utc.copy()
    if choice == "NY close (UTC+2/+3)":
        out.index = out.index.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
    else:
        tz = {
            "Auto (EET)": "Europe/Bucharest",
            "UTC+2": timezone(timedelta(hours=2)),
            "UTC+3": timezone(timedelta(hours=3)),
            "UTC": timezone.utc,
        }[choice]
        out.index = out.index.tz_convert(tz).tz_localize(None)
    return out


def drop_clearing_hour(df_srv, choice):
    if df_srv.empty or choice == "UTC":
        return df_srv
    return df_srv[np.asarray(df_srv.index.hour) != 23]


def is_fx_asset(route):
    sym = route["sym"]
    return ("/" in sym) and ("BTC" not in sym)


def is_crypto_asset(route):
    sym = route["sym"].upper()
    return any(sym.startswith(p) for p in CRYPTO_PREFIXES)


def htf_for(asset_key, tf):
    base = TERMINAL_HTF_MAP.get(tf, tf)
    if is_crypto_asset(ASSET_ROUTER[asset_key]):
        return CRYPTO_HTF_OVERRIDE.get(tf, base)
    return base


def prepare_ohlc(df_utc, tf, is_fx, raw, drop_clearing, server_choice):
    if df_utc.empty:
        return df_utc
    filter_on = is_fx and not raw
    df = df_utc.copy()
    if tf in ("W1", "MN1", "MN3", "MN6", "MN24"):
        df.index = df.index.tz_localize(None)
        if tf in RESAMPLE_RULE:
            df = resample_ohlc(df, RESAMPLE_RULE[tf])
    else:
        if filter_on:
            df = drop_weekend_ny(df)
        if not df.empty:
            df = to_server_time(df, server_choice)
            if filter_on and drop_clearing:
                df = drop_clearing_hour(df, server_choice)
            if tf in RESAMPLE_RULE:
                df = resample_ohlc(df, RESAMPLE_RULE[tf])
            if tf == "D1" and filter_on:
                df = glue_sunday(df)
    if not df.empty:
        df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


@st.cache_data(ttl=300, show_spinner=False)
def fetch_yahoo(sym, interval):
    yf_int, per = YF_MAP[interval]
    try:
        df = yf.download(sym, period=per, interval=yf_int, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame(), E("yahoo_nodata", detail=f"{sym} ({yf_int})")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=lambda x: str(x).capitalize())
        df = df[["Open", "High", "Low", "Close"]].dropna()
        idx = df.index
        df.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
        df = df[~df.index.duplicated(keep="last")].sort_index()
        return df, None
    except Exception as e:
        return pd.DataFrame(), E("exception", detail=safe_err(e))


class TDError(Exception):
    """Ошибка страницы Twelve Data: исключения не кэшируются."""


def _td_request(sym, base_int, end_date=None):
    params = {"symbol": sym, "interval": base_int, "apikey": API_KEY, "outputsize": TD_PAGE_SIZE, "timezone": "UTC"}
    if end_date:
        params["end_date"] = end_date
    try:
        r = requests.get("https://api.twelvedata.com/time_series", params=params, timeout=15)
        res = r.json()
        if "values" not in res:
            return pd.DataFrame(), (E("td", detail=res["message"]) if res.get("message") else E("td_nodata"))
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
        return pd.DataFrame(), E("exception", detail=safe_err(e))


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _td_old_page(sym, base_int, end_date):
    df, err = _td_request(sym, base_int, end_date)
    if err:
        raise TDError(err)
    return df


def _next_monday(ts):
    d = ts.normalize()
    return d + pd.Timedelta(days=(7 - d.dayofweek) % 7 or 7)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_smart_data(asset_key, interval):
    route = ASSET_ROUTER[asset_key]
    if route["prov"] == "yahoo":
        return fetch_yahoo(route["yf"], interval)
    base_int = TF_MAP[BASE_TF.get(interval, interval)]
    df, err = _td_request(route["sym"], base_int)
    if err or df.empty:
        return df, err or E("td_nodata")
    frames, page, partial_err = [df], df, None
    for _ in range(TD_PAGES.get(interval, 1) - 1):
        if len(page) < TD_PAGE_SIZE - 100:
            break
        end = _next_monday(page.index.min())
        try:
            page = _td_old_page(route["sym"], base_int, end.strftime("%Y-%m-%d %H:%M:%S"))
        except TDError as ex:
            err_t = ex.args[0]
            detail = str(err_t[1].get("detail", "")) if isinstance(err_t, tuple) else ""
            if "no data" not in detail.lower():
                partial_err = err_t
            break
        if page.empty:
            break
        frames.append(page)
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out, partial_err


@st.cache_data(ttl=4, show_spinner=False)
def fetch_account_telemetry():
    """Читает последнюю строку public.account_telemetry по Supabase PostgREST.
    Тихий отказ на любой ошибке: None — UI просто покажет OFFLINE.
    """
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
    except Exception:
        return None
    if not url or not key:
        return None
    try:
        r = requests.get(
            f"{url.rstrip('/')}/rest/v1/account_telemetry",
            params={"order": "updated_at.desc", "limit": "1"},
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
            },
            timeout=5,
        )
        if r.status_code != 200:
            return None
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            return None
        return rows[0]
    except Exception:
        return None


def render_telemetry_hud():
    """Институциональный HUD здоровья счёта. Возвращает (is_live, equity_or_None)."""
    row = fetch_account_telemetry()
    if row is None:
        html = (
            "<div class='telemetry-hud telemetry-offline'>"
            "<div class='th-title'>"
            f"<span class='th-dot'></span>{t('telemetry_title')}: {t('telemetry_unavailable')}"
            "</div>"
            "</div>"
        )
        st.markdown(html, unsafe_allow_html=True)
        return False, None

    try:
        updated_at = pd.to_datetime(row.get("updated_at"), utc=True, errors="coerce")
    except Exception:
        updated_at = pd.NaT
    now = pd.Timestamp.now(tz="UTC")
    if pd.notna(updated_at):
        age_sec = float((now - updated_at).total_seconds())
    else:
        age_sec = 99999.0
    is_live = age_sec < TELEMETRY_LIVE_SECONDS

    account = row.get("account_id", "—")
    try:
        balance = float(row.get("balance", 0.0))
        equity = float(row.get("equity", 0.0))
        dd_today = float(row.get("drawdown_today", 0.0))
        dd_total = float(row.get("drawdown_total", 0.0))
    except (TypeError, ValueError):
        balance, equity, dd_today, dd_total = 0.0, 0.0, 0.0, 0.0
    status = str(row.get("status", "—"))

    cap = TELEMETRY_DAILY_CAP
    if dd_today >= cap:
        dd_color = "#9a5252"
    elif dd_today >= cap * 0.7:
        dd_color = ACCENT_MUTED
    else:
        dd_color = "#2c3e50"

    cls = "telemetry-live" if is_live else "telemetry-offline"
    dot_label = t("telemetry_live") if is_live else t("telemetry_offline", m=int(age_sec // 60))
    if pd.notna(updated_at):
        foot = updated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        foot = "—"

    html = (
        f"<div class='telemetry-hud {cls}'>"
        f"<div class='th-title'><span class='th-dot'></span>{t('telemetry_title')}: {dot_label}</div>"
        f"<div class='th-row'>"
        f"<span class='th-k'>Account</span><span class='th-v'>{account}</span>"
        f"<span class='th-k'>Balance</span><span class='th-v'>{fmt_money(balance, 'USD')}</span>"
        f"<span class='th-k'>Equity</span><span class='th-v'>{fmt_money(equity, 'USD')}</span>"
        f"<span class='th-k'>Daily DD</span><span class='th-v' style='color:{dd_color}'>{dd_today:.2f}% (cap {cap:.1f}%)</span>"
        f"<span class='th-k'>Total DD</span><span class='th-v'>{dd_total:.2f}%</span>"
        f"<span class='th-k'>Status</span><span class='th-v'>{status}</span>"
        f"</div>"
        f"<div class='th-foot'>{foot}</div>"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    return is_live, equity if is_live else None


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

    # --- Фракталы с тай-брейком полярности (v1.70) ---
    # Слева нестрогое сравнение, справа строгое: при двойной вершине / плоском пике
    # маркер достаётся ПЕРВОМУ появлению экстремума и не исчезает на обоих барах.
    out["Minor_High"] = (
        (high >= high.shift(1)) & (high > high.shift(2)) &
        (high > high.shift(-1)) & (high > high.shift(-2))
    )
    out["Minor_Low"] = (
        (low <= low.shift(1)) & (low < low.shift(2)) &
        (low < low.shift(-1)) & (low < low.shift(-2))
    )
    out["Major_High"], out["Major_Low"] = True, True
    for i in range(1, 11):
        out["Major_High"] &= (high >= high.shift(i)) & (high > high.shift(-i))
        out["Major_Low"] &= (low <= low.shift(i)) & (low < low.shift(-i))
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


def axis_time_fmt(tf):
    if tf in MN_MONTHS:
        return "%m.%Y"
    if tf in ("D1", "W1"):
        return "%d.%m.%y"
    return "%d.%m %H:%M"


def _forecast_clock(df_plot, tf, is_fx):
    idx = df_plot.index
    if tf in MN_MONTHS or len(idx) < 3:
        return None
    diffs = pd.Series(np.diff(idx.values))
    step = diffs.median()
    if pd.isna(step) or step <= pd.Timedelta(0):
        return None
    anchor = jump = None
    if is_fx and tf != "W1":
        big = diffs[diffs > step * 1.5]
        if len(big):
            gap = big.mode().iloc[0]
            pos = int(diffs[diffs == gap].index[0])
            cand = idx[pos] + step
            anchor = (cand.dayofweek, cand.hour, cand.minute)
            jump = gap - step
    return step, anchor, jump


def bar_time_at(df_plot, x, tf, is_fx, clock=None):
    idx = df_plot.index
    n = len(idx)
    x = int(x)
    if n == 0:
        return pd.Timestamp.now(), True
    if 0 <= x < n:
        return idx[x], False
    if x < 0:
        return idx[0], True
    k = x - (n - 1)
    if tf in MN_MONTHS:
        return idx[-1] + pd.DateOffset(months=MN_MONTHS[tf] * k), True
    clock = _forecast_clock(df_plot, tf, is_fx) if clock is None else clock
    if clock is None:
        return idx[-1] + pd.Timedelta(hours=k), True
    step, anchor, jump = clock
    ts = idx[-1]
    for _ in range(k):
        ts = ts + step
        if anchor is not None and (ts.dayofweek, ts.hour, ts.minute) == anchor:
            ts = ts + jump
    return ts, True


def fmt_bar_time(ts, tf, compact):
    if tf in MN_MONTHS:
        return ts.strftime("%m.%Y" if compact else "%Y-%m")
    if tf in ("D1", "W1"):
        return ts.strftime("%d.%m.%y" if compact else "%Y-%m-%d")
    return ts.strftime("%d.%m %H:%M" if compact else "%Y-%m-%d %H:%M")


def time_target_label(base, ts, forecast, tf, mobile):
    mark = "≈" if forecast else ""
    d = fmt_bar_time(ts, tf, mobile)
    return f"{mark}{base} ({d})"


def hosoda_targets(a, b, c):
    if b > a:
        return {"V": b + (b - c), "N": c + (b - a), "E": b + (b - a), "NT": c + (c - a)}
    return {"V": b - (c - b), "N": c - (a - b), "E": b - (a - b), "NT": c - (a - c)}


def trigger_plan(df, abc, mode, tf, is_fx, last_close):
    """Единый план входа по пробою: уровень, окно, стоп и решение рынок/лимит/наблюдение."""
    if mode not in TRIG_WATCH_BARS or len(abc) != 3 or len(df) < 3:
        return None
    rA, rB, rC = abc
    buy = rB["y"] > rA["y"]
    bars = TRIG_WATCH_BARS[mode]
    ref_t = rC["t"] if mode == "hosoda" else rB["t"]
    if ref_t not in df.index:
        return {"ok": False, "why": "ref_missing"}
    rp = int(df.index.get_loc(ref_t))
    rb = df.iloc[rp]

    atr_last = float(df["ATR"].iloc[-2])
    if not np.isfinite(atr_last):
        atr_last = float(df["ATR"].iloc[-1])
    atr_now = atr_last if np.isfinite(atr_last) else 0.0
    atr_ref = float(rb["ATR"]) if np.isfinite(rb["ATR"]) else atr_now

    if mode == "hosoda":
        level = float(rb["High"]) if buy else float(rb["Low"])
        buf = STOP_BUFFER_ATR * atr_ref
        stop = float(rC["y"]) - buf if buy else float(rC["y"]) + buf
        stop_src = "c"
    else:
        level = float(rB["y"])
        cb = df.iloc[-2]
        sa_v, sb_v = float(cb["senkou_a"]), float(cb["senkou_b"])
        if not (np.isfinite(sa_v) and np.isfinite(sb_v)):
            return {"ok": False, "why": "no_cloud"}
        buf = STOP_BUFFER_ATR * atr_now
        stop = min(sa_v, sb_v) - buf if buy else max(sa_v, sb_v) + buf
        stop_src = "cloud"

    conf_t = None
    if rp + 1 < len(df) - 1:
        seg = df.iloc[rp + 1:-1]
        mask = (seg["Close"] > level) if buy else (seg["Close"] < level)
        hits = np.flatnonzero(mask.to_numpy())
        if len(hits):
            conf_t = df.index[rp + 1 + int(hits[0])]

    clock = _forecast_clock(df, tf, is_fx)
    step = clock[0] if clock else pd.Timedelta(hours=1)
    now_ts = df.index[-1]
    if conf_t is not None:
        expire = bar_time_at(df, len(df) - 1 + bars, tf, is_fx, clock)[0]
    else:
        expire = bar_time_at(df, rp + bars, tf, is_fx, clock)[0] + step

    away = abs(last_close - level)
    dist_atr = (away / atr_now) if atr_now > 0 else None
    at_or_better = (last_close <= level) if buy else (last_close >= level)

    if conf_t is not None:
        if at_or_better or (atr_now > 0 and away <= ATR_CHASE_LIMIT * atr_now):
            dec, entry_eff = "market", last_close
        else:
            dec, entry_eff = "limit", level
    else:
        if expire > now_ts:
            dec, entry_eff = "watch", level
        else:
            dec, entry_eff = "expired", level

    return {"ok": True, "buy": buy, "level": level, "stop": stop, "stop_src": stop_src,
            "ref_t": ref_t, "bars": bars, "expire": expire, "conf_t": conf_t,
            "atr_now": atr_now, "atr_ref": atr_ref, "buf": buf,
            "dec": dec, "entry": entry_eff, "away": away, "dist_atr": dist_atr,
            "target": float(hosoda_targets(rA["y"], rB["y"], rC["y"])["N"])}


ALICE_TARGETS = ("N",)
ALICE_HORIZON = 50
ALICE_HORIZON_MAX = 300
ALICE_LAG = {"minor": 0, "major": 0}     # ZERO-LAG: вход на баре C, без ожидания подтверждений
ALICE_MAJOR_RADIUS = 10
ALICE_SNAP_BARS = 2
ALICE_MAJOR_TOL_ATR = 0.35
ALICE_LIGHT_COLORS = {"green": "#3f7d5c", "yellow": ACCENT_MUTED, "red": "#9a5252"}
ALICE_GREEN_EDGE, ALICE_GREEN_Z, ALICE_GREEN_UPLIFT = 0.05, 2.0, 0.03
ALICE_RED_EDGE, ALICE_RED_Z = 0.10, 2.0
ALICE_MIN_RESOLVED = 0.10
ALICE_MIN_LEG_ATR = 2.0
ALICE_MIN_SAMPLES = 80
ALICE_MIN_FREQ = 30
ALICE_MIN_CLASS = 10
ALICE_MAX_SAMPLES = 500
ALICE_USE_GEOMETRY = True
ALICE_BASE_FEATURES = ["kumo_w", "dist_kijun", "tk_spread", "atr_rel", "htf"]
ALICE_WAVE_FEATURES = ["ab_slope", "c_wick"]
ALICE_GEOM_FEATURES = ["retr", "risk_z", "reward_z"]
ALICE_CLASSES = [("minor", "minor"), ("major", "major"), ("major", "minor"), ("minor", "major")]


def htf_trend_series(df_htf, ltf_index):
    h = add_indicators(df_htf)
    cl = h["Close"].to_numpy(dtype=float)
    tk, kj = h["tenkan"].to_numpy(dtype=float), h["kijun"].to_numpy(dtype=float)
    sa, sb = h["senkou_a"].to_numpy(dtype=float), h["senkou_b"].to_numpy(dtype=float)
    up = (cl > np.maximum(sa, sb)) & (tk >= kj)
    dn = (cl < np.minimum(sa, sb)) & (tk <= kj)
    tr = pd.Series(np.where(up, 1.0, np.where(dn, -1.0, 0.0)), index=h.index).shift(1)
    return tr.reindex(ltf_index, method="ffill").fillna(0.0).to_numpy(dtype=float)


def _alice_arrays(df, htf):
    cols = {"hi": "High", "lo": "Low", "op": "Open", "cl": "Close", "atr": "ATR",
            "tk": "tenkan", "kj": "kijun", "sa": "senkou_a", "sb": "senkou_b"}
    ar = {k: df[c].to_numpy(dtype=float) for k, c in cols.items()}
    ar["htf"] = np.asarray(htf, dtype=float)
    return ar


def _alice_base(ar, e, d):
    """Признаки Ишимоку на баре e — строго причинно (бары <= e)."""
    atr, cl = ar["atr"][e], ar["cl"][e]
    if not (np.isfinite(atr) and atr > 0 and np.isfinite(cl) and cl > 0):
        return None
    v = [
        (ar["sa"][e] - ar["sb"][e]) / atr * d,
        (cl - ar["kj"][e]) / atr * d,
        (ar["tk"][e] - ar["kj"][e]) / atr * d,
        atr / cl,
        ar["htf"][e] * d,
    ]
    return v if np.all(np.isfinite(v)) else None


def _alice_wave(ar, a, b, c, Ap, Bp, atr):
    """Причинные признаки формы волны: наклон AB (ATR на бар) и доля теней свечи C."""
    bars = max(1, b - a)
    slope = (Bp - Ap) / bars / atr if atr > 0.0 else 0.0
    hi, lo = ar["hi"][c], ar["lo"][c]
    op, cl = ar["op"][c], ar["cl"][c]
    rng = hi - lo
    body = abs(cl - op)
    wick = (rng - body) / rng if rng > 0.0 else 0.0
    if not np.isfinite(slope):
        slope = 0.0
    if not np.isfinite(wick):
        wick = 0.0
    return [float(slope), float(min(max(wick, 0.0), 1.0))]


def _alice_horizon(c, a):
    return int(min(ALICE_HORIZON_MAX, max(ALICE_HORIZON, c - a)))


def _alice_geom(entry, atr, horizon, Ap, Bp, Cp, T):
    scale = atr * np.sqrt(horizon)
    return [(Bp - Cp) / (Bp - Ap), (entry - Cp) / scale, (T - entry) / scale]


def _alice_label(hi_m, lo_m, e, target, stop, horizon):
    th = hi_m[e + 1:e + horizon + 1] >= target
    sh = lo_m[e + 1:e + horizon + 1] <= stop
    ti = int(np.argmax(th)) if th.any() else horizon + 1
    si = int(np.argmax(sh)) if sh.any() else horizon + 1
    if ti < si:
        return 1
    return -1 if si <= horizon else 0


def _alice_pivots(df, d, cls, strict=False):
    pref = "Major" if cls == "major" else "Minor"
    low_col, high_col = (pref + "_Low", pref + "_High") if d > 0 else (pref + "_High", pref + "_Low")
    lows, highs = df[low_col].to_numpy(dtype=bool), df[high_col].to_numpy(dtype=bool)
    if strict and cls == "minor":
        lows = lows & ~df["Major_Low" if d > 0 else "Major_High"].to_numpy(dtype=bool)
        highs = highs & ~df["Major_High" if d > 0 else "Major_Low"].to_numpy(dtype=bool)
    return np.flatnonzero(lows), np.flatnonzero(highs)


def alice_build_samples(df, htf, targets, ab_cls, c_cls, strict=True, strict_ab=None):
    """Исторические волны; ZERO-LAG: вход на закрытии бара C, исход — строго после C."""
    strict_ab = strict if strict_ab is None else strict_ab
    ar = _alice_arrays(df, htf)
    n, lag = len(df), ALICE_LAG[c_cls]
    rows = []
    for d in (1, -1):
        hi_m, lo_m, cl_m = (ar["hi"], ar["lo"], ar["cl"]) if d > 0 else (-ar["lo"], -ar["hi"], -ar["cl"])
        if ab_cls == "major":
            lows_ab, highs_ab = _alice_pivots(df, d, "major")
        else:
            lows_ab = _alice_pivots(df, d, "minor")[0]
            highs_ab = _alice_pivots(df, d, "minor", strict_ab)[1]
        lows_c, _ = _alice_pivots(df, d, c_cls, strict)
        for b in highs_ab:
            j = int(np.searchsorted(lows_ab, b)) - 1
            if j < 0:
                continue
            a = int(lows_ab[j])
            Ap, Bp = lo_m[a], hi_m[b]
            above = np.flatnonzero(hi_m[b + 1:] > Bp)
            end = n if len(above) == 0 else b + 1 + int(above[0])
            deepest = np.inf
            for c in lows_c[(lows_c >= b + 3) & (lows_c < end)]:
                c = int(c)
                Cp = lo_m[c]
                deepest = min(deepest, lo_m[b + 1:c].min())
                if Cp > deepest:
                    continue
                e = c + lag
                H = _alice_horizon(c, a)
                if e + H >= n:
                    continue
                atr = ar["atr"][e]
                leg = Bp - Ap
                if not (np.isfinite(atr) and atr > 0 and leg >= ALICE_MIN_LEG_ATR * atr and Ap < Cp < Bp):
                    continue
                base, entry = _alice_base(ar, e, d), cl_m[e]
                if base is None:
                    continue
                wave = _alice_wave(ar, a, b, c, Ap, Bp, atr)
                tg = hosoda_targets(Ap, Bp, Cp)
                row = {"c": c, "b": b, "e": e, "h": H, "d": d,
                       "ab_major": 1.0 if ab_cls == "major" else 0.0, "c_major": 1.0 if c_cls == "major" else 0.0}
                row.update(zip(ALICE_BASE_FEATURES, base))
                row.update(zip(ALICE_WAVE_FEATURES, wave))
                for name in targets:
                    T = tg[name]
                    geom = _alice_geom(entry, atr, H, Ap, Bp, Cp, T)
                    if name == targets[0]:
                        row["retr"], row["risk_z"] = geom[0], geom[1]
                    row["reward_z_" + name] = geom[2]
                    row["y_" + name] = _alice_label(hi_m, lo_m, e, T, Cp, H)
                rows.append(row)
    return pd.DataFrame(rows)


def _alice_fit(X, y):
    return RandomForestClassifier(
        n_estimators=100, max_depth=5, min_samples_leaf=8, random_state=42, n_jobs=1
    ).fit(X, y)


def alice_reliability(n, auc, uplift):
    if auc is None:
        return "low"
    ok_high = uplift is None or uplift >= 0.05
    ok_mod = uplift is None or uplift >= 0.03
    if n >= 400 and auc >= 0.60 and ok_high:
        return "high"
    if n >= 250 and auc >= 0.55 and ok_mod:
        return "mod"
    return "low"


def _alice_train_rows(samples, name, e):
    if not len(samples) or ("y_" + name) not in samples:
        return samples.iloc[0:0] if len(samples) else samples
    tr = samples[(samples["e"] + samples["h"] <= e) & samples["y_" + name].notna()]
    return tr.sort_values("e").tail(ALICE_MAX_SAMPLES)


def _alice_matrix(tr, name):
    """Ишимоку + форма волны + геометрия + классы. Порядок совпадает с вектором инференса."""
    X = tr[ALICE_BASE_FEATURES].to_numpy(dtype=float)
    X = np.column_stack([X, tr[ALICE_WAVE_FEATURES].to_numpy(dtype=float)])
    if ALICE_USE_GEOMETRY:
        X = np.column_stack([X, tr[["retr", "risk_z", "reward_z_" + name]].to_numpy(dtype=float)])
    return np.column_stack([X, tr[["ab_major", "c_major"]].to_numpy(dtype=float)])


def alice_point_class(df, i, high_side, price):
    n, R = len(df), ALICE_MAJOR_RADIUS
    if i + R >= n:
        return "pending"
    flags = df["Major_High" if high_side else "Major_Low"].to_numpy(dtype=bool)
    if flags[max(0, i - ALICE_SNAP_BARS):i + ALICE_SNAP_BARS + 1].any():
        return "major"
    if i < R:
        return "minor"
    window = df["High" if high_side else "Low"].to_numpy(dtype=float)[i - R:i + R + 1]
    atr = float(df["ATR"].iloc[i])
    if not (np.isfinite(atr) and atr > 0):
        return "minor"
    gap = (window.max() - price) if high_side else (price - window.min())
    return "major" if gap <= ALICE_MAJOR_TOL_ATR * atr else "minor"


def _alice_proba3(model, X):
    P = np.zeros((len(X), 3))
    raw = model.predict_proba(X)
    for j, cls in enumerate(model.classes_):
        P[:, int(cls) + 1] = raw[:, j]
    return P


def _alice_fair(P):
    res = P[:, 0] + P[:, 2]
    return np.where(res > 1e-9, P[:, 2] / np.maximum(res, 1e-9), 0.5)


def _alice_counts(y):
    return {1: int((y == 1).sum()), -1: int((y == -1).sum()), 0: int((y == 0).sum())}


def _alice_neff(tr):
    return max(1, int(tr[["d", "b"]].drop_duplicates().shape[0]))


def _alice_edge(p_fair, entry, Cp, T, n_eff, res_share):
    risk, reward = abs(entry - Cp), abs(T - entry)
    be = risk / (risk + reward) if (risk + reward) > 0 else 0.5
    n_res = max(1.0, n_eff * max(res_share, 0.05))
    p = min(max(p_fair, 0.01), 0.99)
    return {"be": be, "edge": p_fair - be, "rr": (reward / risk) if risk > 0 else None,
            "se": float(np.sqrt(p * (1 - p) / n_res)), "n_eff": int(n_eff), "res_share": float(res_share)}


def _alice_result(meta, P, m, counts, auc, uplift, pooled, freq_only, n_eff, entry, Cp, T):
    p_s, p_0, p_t = (float(v) for v in P)
    p_fair = p_t / (p_t + p_s) if (p_t + p_s) > 1e-9 else 0.5
    res_share = (counts[1] + counts[-1]) / m
    return {**meta, "status": "ok", "det": None, "p_target": p_t, "p_stop": p_s, "p_timeout": p_0, "p_fair": p_fair,
            "n": m, "freq": {"target": counts[1] / m, "stop": counts[-1] / m, "timeout": counts[0] / m},
            "auc": auc, "uplift": uplift, "reliability": alice_reliability(m, auc, uplift),
            "pooled": pooled, "freq_only": freq_only, **_alice_edge(p_fair, entry, Cp, T, n_eff, res_share)}


def _alice_det_result(kind, meta, entry, Cp, T):
    pt, ps = (1.0, 0.0) if kind == "target" else (0.0, 1.0)
    return {**meta, "status": "ok", "det": kind, "p_target": pt, "p_stop": ps, "p_timeout": 0.0, "p_fair": pt, "n": 0,
            "freq": None, "auc": None, "uplift": None, "reliability": "low", "pooled": False, "freq_only": False,
            **_alice_edge(pt, entry, Cp, T, 1, 1.0), "se": 0.0}


def alice_verdict(r):
    if r["det"] == "target":
        return "green"
    if r["det"] == "stop":
        return "red"
    if r["res_share"] < ALICE_MIN_RESOLVED:
        return "yellow"
    edge, se, upl = r["edge"], r["se"], r["uplift"]
    z = edge / se if se > 0 else 0.0
    if edge >= ALICE_GREEN_EDGE and z >= ALICE_GREEN_Z and upl is not None and upl >= ALICE_GREEN_UPLIFT:
        return "green"
    if edge <= -ALICE_RED_EDGE and z <= -ALICE_RED_Z:
        return "red"
    return "yellow"


def alice_predict(df, htf, a_t, a_y, b_t, b_y, c_t, c_y, targets=ALICE_TARGETS):
    """ZERO-LAG инференс: вход на баре C, признаки по барам <= C. Отдаёт Edge мгновенно."""
    if not SKLEARN_OK:
        return {"status": "sklearn"}
    n = len(df)
    try:
        a, b, c = (int(df.index.get_loc(t_)) for t_ in (a_t, b_t, c_t))
    except KeyError:
        return {"status": "nan"}
    d = 1 if b_y > a_y else -1
    if not (a < b < c):
        return {"status": "geom"}
    a_st = alice_point_class(df, a, d < 0, a_y)
    b_st = alice_point_class(df, b, d > 0, b_y)
    c_st = alice_point_class(df, c, d < 0, c_y)
    ab_cls = "major" if b_st == "major" else "minor"
    c_cls = "major" if c_st == "major" else "minor"
    lag = ALICE_LAG[c_cls]
    e = min(c + lag, n - 1)
    Ap, Bp, Cp = d * a_y, d * b_y, d * c_y
    if not (Ap < Cp < Bp):
        return {"status": "geom"}
    ar = _alice_arrays(df, htf)
    entry, atr = d * ar["cl"][e], ar["atr"][e]
    base = _alice_base(ar, e, d)
    if base is None:
        return {"status": "nan"}
    wave = _alice_wave(ar, a, b, c, Ap, Bp, atr)
    H = _alice_horizon(c, a)
    tg = hosoda_targets(Ap, Bp, Cp)
    strict_c, strict_ab = c_st != "pending", b_st != "pending"
    meta = {"h": H, "lag": lag, "cls": c_cls, "ab": ab_cls, "strict": strict_c,
            "a_st": a_st, "b_st": b_st, "c_st": c_st}
    own = pool = None
    out = {}
    for name in targets:
        T = tg[name]
        if entry <= Cp:
            out[name] = _alice_det_result("stop", meta, entry, Cp, T)
            continue
        if T <= entry:
            out[name] = _alice_det_result("target", meta, entry, Cp, T)
            continue
        if own is None:
            own = alice_build_samples(df, htf, targets, ab_cls, c_cls, strict_c, strict_ab)
        tr, pooled = _alice_train_rows(own, name, e), False
        if ALICE_MIN_FREQ <= len(tr) < ALICE_MIN_SAMPLES:
            cnt = _alice_counts(tr["y_" + name].to_numpy(dtype=int))
            if min(cnt[1], cnt[-1]) < ALICE_MIN_CLASS:
                P = np.array([cnt[-1] + 1, cnt[0] + 1, cnt[1] + 1], dtype=float) / (len(tr) + 3)
                out[name] = _alice_result(meta, P, len(tr), cnt, None, None, False, True, _alice_neff(tr), entry, Cp, T)
                continue
        if len(tr) < ALICE_MIN_SAMPLES:
            if pool is None:
                parts = [own] + [alice_build_samples(df, htf, targets, ab, cc, strict_c, strict_ab)
                                 for ab, cc in ALICE_CLASSES if (ab, cc) != (ab_cls, c_cls)]
                parts = [p_ for p_ in parts if len(p_)]
                pool = pd.concat(parts, ignore_index=True) if parts else own
            tr, pooled = _alice_train_rows(pool, name, e), True
        m = len(tr)
        if m < ALICE_MIN_SAMPLES:
            out[name] = {"status": "samples", "kw": {"n": m, "min": ALICE_MIN_SAMPLES}}
            continue
        y = tr["y_" + name].to_numpy(dtype=int)
        cnt = _alice_counts(y)
        n_eff = _alice_neff(tr)
        if min(cnt[1], cnt[-1]) < ALICE_MIN_CLASS:
            P = np.array([cnt[-1] + 1, cnt[0] + 1, cnt[1] + 1], dtype=float) / (m + 3)
            out[name] = _alice_result(meta, P, m, cnt, None, None, pooled, True, n_eff, entry, Cp, T)
            continue
        X = _alice_matrix(tr, name)
        x = np.asarray(base + wave, dtype=float)
        if ALICE_USE_GEOMETRY:
            x = np.append(x, _alice_geom(entry, atr, H, Ap, Bp, Cp, T))
        x = np.append(x, [1.0 if ab_cls == "major" else 0.0, 1.0 if c_cls == "major" else 0.0])
        e_arr, h_arr = tr["e"].to_numpy(), tr["h"].to_numpy()
        e_cut = e_arr[int(m * 0.75)]
        fit_i, val_i = np.flatnonzero(e_arr + h_arr < e_cut), np.flatnonzero(e_arr >= e_cut)
        auc = uplift = None
        if len(fit_i) >= 40 and len(val_i) >= 15:
            yf, yv = y[fit_i], y[val_i]
            res_v = yv != 0
            if res_v.sum() >= 10 and 0 < (yv[res_v] == 1).sum() < res_v.sum() and (yf == 1).any() and (yf == -1).any():
                Xv = X[val_i][res_v]
                auc = float(roc_auc_score(yv[res_v] == 1, _alice_fair(_alice_proba3(_alice_fit(X[fit_i], yf), Xv))))
                if ALICE_USE_GEOMETRY:
                    gcols = slice(len(ALICE_BASE_FEATURES), None)
                    auc_geom = float(roc_auc_score(
                        yv[res_v] == 1, _alice_fair(_alice_proba3(_alice_fit(X[fit_i][:, gcols], yf), Xv[:, gcols]))))
                    uplift = auc - auc_geom
        P = _alice_proba3(_alice_fit(X, y), x.reshape(1, -1))[0]
        out[name] = _alice_result(meta, P, m, cnt, auc, uplift, pooled, False, n_eff, entry, Cp, T)
    return {"status": "ok", "targets": out}


@st.cache_data(ttl=600, show_spinner=False)
def alice_run(df, htf, a_t, a_y, b_t, b_y, c_t, c_y, targets):
    return alice_predict(df, htf, a_t, a_y, b_t, b_y, c_t, c_y, targets)


def _tg_credentials():
    try:
        return str(st.secrets["TELEGRAM_TOKEN"]), str(st.secrets["TELEGRAM_CHAT_ID"])
    except Exception:
        return None, None


def _mt5_secret():
    try:
        return str(st.secrets.get("MT5_SECRET_TOKEN", MT5_DEFAULT_TOKEN))
    except Exception:
        return MT5_DEFAULT_TOKEN


def send_mt5_order(payload, confirm_label):
    token, chat_id = _tg_credentials()
    if not token or not chat_id:
        return False, t("mt5_no_secrets")
    text = "/order " + json.dumps(payload, separators=(",", ":"))
    keyboard = {"inline_keyboard": [[{"text": confirm_label, "callback_data": MT5_EXEC_MARK}]]}
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat_id, "text": text,
                                "reply_markup": json.dumps(keyboard, separators=(",", ":")),
                                "disable_web_page_preview": "true"},
                          timeout=20)
        res = r.json()
        if not res.get("ok"):
            return False, safe_err(str(res.get("description", "unknown error")))
        return True, None
    except Exception as e:
        return False, safe_err(e)


def _render_chart_matplotlib(df_plot, pts, targets, title, tf, is_fx, mobile):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.arange(len(df_plot))
    o, h, l, c = (df_plot[k].to_numpy(dtype=float) for k in ("Open", "High", "Low", "Close"))
    fig_, ax = plt.subplots(figsize=(14, 7.5), dpi=130)
    ax.vlines(x, l, h, color="#2c3e50", linewidth=0.8, zorder=3)
    ax.bar(x, np.abs(c - o), bottom=np.minimum(o, c), width=0.6, color=np.where(c >= o, "white", "#2c3e50"),
           edgecolor="#2c3e50", linewidth=0.8, zorder=4)
    ax.plot(x, df_plot["tenkan"].to_numpy(dtype=float), color="#2980b9", linewidth=1.2, zorder=5)
    ax.plot(x, df_plot["kijun"].to_numpy(dtype=float), color="#e74c3c", linewidth=1.6, zorder=5)
    ax.plot(x, df_plot["chikou"].to_numpy(dtype=float), color="#1e8449", linewidth=1.0, zorder=5)
    sa, sb = df_plot["raw_senkou_a"].to_numpy(dtype=float), df_plot["raw_senkou_b"].to_numpy(dtype=float)
    ax.fill_between(x + 26, sa, sb, where=sa >= sb, color="#2ecc71", alpha=0.25, linewidth=0, zorder=1)
    ax.fill_between(x + 26, sa, sb, where=sa < sb, color="#e74c3c", alpha=0.20, linewidth=0, zorder=1)
    if len(pts) >= 3:
        A_, B_, C_ = pts[:3]
        ax.plot([p_["x"] for p_ in [A_, B_, C_]], [p_["y"] for p_ in [A_, B_, C_]], color="#f39c12", marker="o", markersize=5, linewidth=1.6, zorder=6)
        # Динамическая полярность подписей — над High или под Low свечи.
        for letter, p_ in zip("ABC", [A_, B_, C_]):
            bar_row = df_plot.iloc[int(p_["x"])]
            is_high = abs(p_["y"] - float(bar_row["High"])) <= abs(p_["y"] - float(bar_row["Low"]))
            if is_high:
                y_anchor = float(bar_row["High"])
                y_offset = 8
                va_mode = "bottom"
            else:
                y_anchor = float(bar_row["Low"])
                y_offset = -12
                va_mode = "top"
            ax.annotate(
                letter, (p_["x"], y_anchor),
                textcoords="offset points", xytext=(0, y_offset),
                ha="center", va=va_mode, fontsize=10, fontweight="bold",
                color=ACCENT_MUTED,
                bbox=dict(boxstyle="round,pad=0.1", facecolor="white", edgecolor="none", alpha=0.7),
            )
        if len(pts) >= 4:
            O_ = pts[3]
            if O_["x"] != A_["x"] or O_["y"] != A_["y"]:
                ax.plot([O_["x"]], [O_["y"]], marker="D", markersize=7,
                        color=ORIGIN_COLOR, linestyle="none", zorder=6, clip_on=True)
                bar_row = df_plot.iloc[int(O_["x"])]
                is_high = abs(O_["y"] - float(bar_row["High"])) <= abs(O_["y"] - float(bar_row["Low"]))
                y_anchor = float(bar_row["High"]) if is_high else float(bar_row["Low"])
                y_offset = 8 if is_high else -12
                va_mode = "bottom" if is_high else "top"
                ax.annotate(
                    "O", (O_["x"], y_anchor),
                    textcoords="offset points", xytext=(0, y_offset),
                    ha="center", va=va_mode, fontsize=10, fontweight="bold",
                    color=ORIGIN_COLOR,
                    bbox=dict(boxstyle="round,pad=0.1", facecolor="white", edgecolor="none", alpha=0.7),
                )
    colors = {"V": "orange", "N": "green", "E": "red", "NT": "purple"}
    for name, val in (targets or {}).items():
        ax.axhline(val, color=colors.get(name, "gray"), linestyle="--", linewidth=1.0, zorder=2)
        ax.text(1.0, val, f" {name} {fmt_price(val)}", transform=ax.get_yaxis_transform(), va="center", fontsize=9, color=colors.get(name, "gray"))

    x_right = float(len(df_plot) - 1)
    if len(pts) >= 3:
        A_, B_, C_ = pts[:3]
        cx = float(C_["x"])
        x_right = max(x_right, cx + TIME_AXIS_FORWARD_BARS)
        time_ab, time_ac = abs(B_["x"] - A_["x"]), abs(C_["x"] - A_["x"])
        clock = _forecast_clock(df_plot, tf, is_fx)

        def vlabel(x_pos, text_, color, y_frac, size=7):
            ax.text(x_pos, y_frac, text_, transform=ax.get_xaxis_transform(), rotation=90,
                    ha="center", va="center", fontsize=size, color=color, zorder=7, clip_on=True,
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.75))

        for x_pos, base, col, y_frac in ((cx + time_ab, f"AB {int(time_ab)}", "blue", 0.30),
                                         (cx + time_ac, f"AC {int(time_ac)}", "teal", 0.30)):
            if x_pos > x_right:
                continue
            ts_, fc_ = bar_time_at(df_plot, x_pos, tf, is_fx, clock)
            ax.axvline(x_pos, color=col, linestyle=":", linewidth=1.1, zorder=2)
            vlabel(x_pos, time_target_label(base, ts_, fc_, tf, mobile), col, y_frac, 8)
        origin_x = pts[3]["x"] if len(pts) >= 4 else pts[0]["x"]
        for k in KIHON_SUU:
            xk = origin_x + k - 1
            if xk > x_right:
                continue
            ts_, fc_ = bar_time_at(df_plot, xk, tf, is_fx, clock)
            ax.axvline(xk, color="gray", linestyle="--", linewidth=0.8, alpha=0.35, zorder=2)
            vlabel(xk, time_target_label(str(k), ts_, fc_, tf, mobile), "#7f8c8d", 0.78, 7)

    cand_ = candidate_c_extreme(df_plot)
    if cand_:
        ax.plot([cand_["x"]], [cand_["y"]], marker="o", markersize=4,
                color=CAND_C_COLOR, linestyle="none", zorder=6, clip_on=True)

    ax.set_xlim(-1.5, x_right + max(2.0, 0.01 * (x_right + 1.0)))
    step = max(1, len(df_plot) // 10)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(df_plot.index.strftime("%Y-%m-%d %H:%M")[::step], rotation=45, ha="right", fontsize=8)
    ax.yaxis.tick_right()
    ax.set_title(title, loc="left", fontsize=11, color="#2c3e50")
    ax.grid(True, color="#f0f0f0")
    for side in ("top", "left"):
        ax.spines[side].set_visible(False)
    buf = io.BytesIO()
    fig_.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig_)
    buf.seek(0)
    return buf


def render_chart_png(fig, df_plot, pts, targets, title, tf, is_fx, mobile):
    try:
        return io.BytesIO(fig.to_image(format="png", width=1400, height=800, scale=2)), "plotly"
    except Exception:
        pass
    try:
        return _render_chart_matplotlib(df_plot, pts, targets, title, tf, is_fx, mobile), "matplotlib"
    except Exception:
        return None, None


def send_telegram(token, chat_id, text, png):
    base = f"https://api.telegram.org/bot{token}"
    try:
        if png is not None:
            png.seek(0)
            r = requests.post(base + "/sendPhoto", data={"chat_id": chat_id, "caption": text[:1000]},
                              files={"photo": ("chart.png", png, "image/png")}, timeout=30)
        else:
            r = requests.post(base + "/sendMessage", data={"chat_id": chat_id, "text": text}, timeout=30)
        res = r.json()
        if not res.get("ok"):
            return False, safe_err(str(res.get("description", "unknown error")))
        return True, None
    except Exception as e:
        return False, safe_err(e)


def refresh_button(key):
    """Компактная иконка ↻: чистит кэши котировок и телеметрии, точки и цели сохраняет."""
    if st.button(t("refresh"), key=key, help=t("refresh_help")):
        fetch_smart_data.clear()
        fetch_yahoo.clear()
        fetch_account_telemetry.clear()
        st.rerun()


PERSIST_KEYS = ["w_mode", "w_server", "w_raw", "w_clear", "w_symbol", "w_tf", "w_radar_tf", "w_radar_active",
                "risk_pct", "account_deposit", "entry_mode", "custom_entry"]


def _on_lang_change():
    st.session_state["_keep"] = {k: st.session_state[k] for k in PERSIST_KEYS if k in st.session_state}


_keep = st.session_state.pop("_keep", None)
if _keep:
    for _k, _v in _keep.items():
        st.session_state[_k] = _v

if "lang" not in st.session_state:
    st.session_state["lang"] = detect_default_lang()
st.session_state.setdefault("w_tf", "H1")
st.session_state.setdefault("w_radar_tf", "D1")
st.session_state.setdefault("w_radar_active", True)
st.session_state.setdefault("risk_pct", RISK_PCT_DEFAULT)
st.session_state.setdefault("account_deposit", 10000.0)
st.session_state.setdefault("entry_mode", "hosoda")

_teleport = st.session_state.pop("_teleport", None)
if _teleport:
    if _teleport.get("asset") in ASSET_ROUTER:
        st.session_state["w_symbol"] = _teleport["asset"]
    if _teleport.get("tf") in TF_MAP:
        st.session_state["w_tf"] = _teleport["tf"]
    st.session_state["w_mode"] = "terminal"
    reset_points()

with st.sidebar:
    lang_label = st.radio("Language / Язык", list(LANGS.keys()), horizontal=True, key="lang", on_change=_on_lang_change)
    LANG = LANGS[lang_label]
    st.markdown("---")
    st.markdown(f"### {t('nav')}")
    app_mode = st.radio(t("module"), ["radar", "terminal"], format_func=lambda k: t("mode_" + k), key="w_mode")
    st.markdown("---")
    st.markdown(f"### {t('data_settings')}")
    offset_choice = st.selectbox(t("server_time"), SERVER_CHOICES, key="w_server")
    count_weekend = st.checkbox(t("raw"), help=t("raw_help"), key="w_raw")
    drop_clearing = st.checkbox(t("clearing"), disabled=count_weekend, help=t("clearing_help"), key="w_clear")

    # --- ТЕЛЕМЕТРИЯ MT5 (HUD здоровья счёта): только в режиме терминала ---
    telemetry_live_flag = False
    telemetry_live_equity = None
    if app_mode == "terminal":
        st.markdown("---")
        telemetry_live_flag, telemetry_live_equity = render_telemetry_hud()

MOBILE = detect_mobile_ua()
inject_css(MOBILE)

if app_mode == "radar":
    st.markdown(f"<h2 class='app-title'>{t('scanner_title')}</h2>", unsafe_allow_html=True)
    if st.session_state.get("w_radar_tf") not in radar_tfs:
        st.session_state["w_radar_tf"] = "D1"
    radar_tf = st.selectbox(t("select_tf"), radar_tfs, key="w_radar_tf")

    def fetch_radar(route, tf):
        df, err = fetch_yahoo(route["yf"], tf)
        if err or df.empty:
            return df, err or E("nodata")
        df = prepare_ohlc(df, tf, is_fx_asset(route), count_weekend, drop_clearing, offset_choice)
        if df.empty:
            return df, E("no_processed")
        return df, None

    def scan_one(asset_name, route, tf):
        try:
            if is_crypto_asset(route) and tf == "MN3":
                return None, E("crypto_hist", tf=tf)
            htf_radar = htf_for(asset_name, tf)
            df_ltf, err_l = fetch_radar(route, tf)
            df_htf, err_h = fetch_radar(route, htf_radar)
            if err_l or err_h:
                return None, err_l or err_h
            if len(df_ltf) < MIN_LTF_BARS or len(df_htf) < MIN_HTF_BARS:
                return None, E("few_bars", ltf=len(df_ltf), min_ltf=MIN_LTF_BARS, htf=len(df_htf), min_htf=MIN_HTF_BARS)
            df_ltf = add_indicators(df_ltf)
            df_htf = add_indicators(df_htf)
            h_c = df_htf.iloc[-2]
            l_c = df_ltf.iloc[-2]
            cur = df_ltf.iloc[-1]
            p_b = df_ltf.iloc[-28]
            h_v = h_c[["Close", "tenkan", "kijun", "senkou_a", "senkou_b"]].astype(float)
            l_v = l_c[["Close", "tenkan", "kijun", "senkou_a", "senkou_b", "ATR"]].astype(float)
            p_v = p_b[["High", "Low", "senkou_a", "senkou_b"]].astype(float)
            c_v = cur[["Close", "High", "Low"]].astype(float)
            if h_v.isna().any() or l_v.isna().any() or p_v.isna().any() or c_v.isna().any():
                return None, E("nan")

            h_kumo_top = max(h_v["senkou_a"], h_v["senkou_b"])
            h_kumo_bot = min(h_v["senkou_a"], h_v["senkou_b"])
            htf_bullish = h_v["Close"] > h_kumo_top and h_v["tenkan"] >= h_v["kijun"]
            htf_bearish = h_v["Close"] < h_kumo_bot and h_v["tenkan"] <= h_v["kijun"]
            trend_code = "up" if htf_bullish else ("down" if htf_bearish else "flat")

            pr, kijun = l_v["Close"], l_v["kijun"]
            zone = l_v["ATR"] * KIJUN_ZONE_ATR
            l_kumo_top = max(l_v["senkou_a"], l_v["senkou_b"])
            l_kumo_bot = min(l_v["senkou_a"], l_v["senkou_b"])
            p_kumo_top = max(p_v["senkou_a"], p_v["senkou_b"])
            p_kumo_bot = min(p_v["senkou_a"], p_v["senkou_b"])
            chikou_buy = pr > p_v["High"] and pr > p_kumo_top
            chikou_sell = pr < p_v["Low"] and pr < p_kumo_bot
            bullish = l_v["tenkan"] > kijun and pr > l_kumo_top and chikou_buy
            bearish = l_v["tenkan"] < kijun and pr < l_kumo_bot and chikou_sell

            pr_live, high_live, low_live = float(c_v["Close"]), float(c_v["High"]), float(c_v["Low"])
            in_zone = abs(pr_live - kijun) <= zone
            near_buy = in_zone or (low_live <= kijun + zone and pr_live >= kijun - zone)
            near_sell = in_zone or (high_live >= kijun - zone and pr_live <= kijun + zone)

            sig = "wait"
            if bullish and near_buy:
                sig = "strong_buy" if htf_bullish else "local_buy"
            elif bearish and near_sell:
                sig = "strong_sell" if htf_bearish else "local_sell"

            diag = None
            if sig == "wait":
                dist = abs(pr_live - kijun)
                if l_v["tenkan"] == kijun:
                    diag = ("flat", {})
                else:
                    buy_side = l_v["tenkan"] > kijun
                    hit = near_buy if buy_side else near_sell
                    if not hit:
                        diag = ("distance", {"dist": dist, "zone": zone, "gap": max(0.0, dist - zone)})
                    else:
                        ok_kumo = pr > l_kumo_top if buy_side else pr < l_kumo_bot
                        ok_chikou = chikou_buy if buy_side else chikou_sell
                        fails = [f for f, ok in (("kumo", ok_kumo), ("chikou", ok_chikou)) if not ok]
                        if fails:
                            diag = ("zone", {"fails": fails})

            return {
                "asset": asset_name, "tf": tf, "sig": sig, "trend": trend_code,
                "price": fmt_price(pr_live), "kijun": fmt_price(kijun), "diag": diag,
            }, None
        except Exception as e:
            return None, E("exception", detail=safe_err(e))

    def run_scan(tf_list):
        total = len(ASSET_ROUTER) * len(tf_list)
        my_bar = st.progress(0, text=t("scanning"))
        results, skipped, done = [], [], 0
        for tf in tf_list:
            for asset_name, route in ASSET_ROUTER.items():
                done += 1
                label = (t("processing", asset=asset_label(asset_name)) if len(tf_list) == 1
                         else t("processing_tf", asset=asset_label(asset_name), tf=tf))
                my_bar.progress(done / total, text=label)
                rec, err = scan_one(asset_name, route, tf)
                if rec:
                    results.append(rec)
                else:
                    skipped.append((asset_name, tf, err))
        my_bar.empty()
        return results, skipped

    if st.button(t("run_scan"), **WIDE):
        res, sk = run_scan([radar_tf])
        st.session_state["radar_out2"] = {
            "ctx": (radar_tf, offset_choice, count_weekend, drop_clearing),
            "all": False, "results": res, "skipped": sk,
        }
    if st.button(t("run_scan_all"), **WIDE):
        res, sk = run_scan(radar_tfs)
        st.session_state["radar_out2"] = {
            "ctx": ("ALL", offset_choice, count_weekend, drop_clearing),
            "all": True, "results": res, "skipped": sk,
        }

    only_active = st.checkbox(t("filter_active"), key="w_radar_active")

    out = st.session_state.get("radar_out2")
    if out:
        scan_tag = "ALL" if out["all"] else radar_tf
        if out["ctx"] != (scan_tag, offset_choice, count_weekend, drop_clearing):
            st.caption(t("stale_scan"))
        asset_order = {name: i for i, name in enumerate(ASSET_ROUTER)}
        rows = out["results"]
        if only_active:
            rows = [r for r in rows if r["sig"] != "wait"]
        rows = sorted(rows, key=lambda r: (r["sig"] == "wait", asset_order[r["asset"]], radar_tfs.index(r["tf"])))
        if rows:
            show_reason = any(r["sig"] == "wait" for r in rows)
            records = []
            for r in rows:
                rec = {t("col_asset"): asset_label(r["asset"])}
                if out["all"]:
                    rec[t("col_tf")] = r["tf"]
                rec[t("col_signal")] = t("sig_" + r["sig"])
                rec[t("col_htf")] = t("trend_" + r["trend"])
                rec[t("col_price")] = r["price"]
                rec[t("col_kijun")] = r["kijun"]
                if show_reason:
                    rec[t("col_reason")] = fmt_diag(r.get("diag"))
                records.append(rec)
            radar_event = st.dataframe(
                pd.DataFrame(records), hide_index=True,
                on_select="rerun", selection_mode="single-row", key="radar_table", **WIDE,
            )
            try:
                sel_rows = list(radar_event.selection.rows)
            except Exception:
                sel_rows = []
            if sel_rows:
                sel_idx = int(sel_rows[0])
                if 0 <= sel_idx < len(rows):
                    picked = rows[sel_idx]
                    tp_asset, tp_tf = picked["asset"], picked["tf"]
                    if st.button(t("teleport", asset=asset_label(tp_asset), tf=tp_tf),
                                 key="teleport_btn", **WIDE):
                        st.session_state["_teleport"] = {"asset": tp_asset, "tf": tp_tf}
                        st.rerun()
        elif out["results"]:
            st.info(t("no_setups"))
        else:
            st.warning(t("no_data"))
        if out["skipped"]:
            with st.expander(t("skipped", n=len(out["skipped"]))):
                if out["all"]:
                    sk_df = pd.DataFrame([(asset_label(a_), tf_, fmt_err(e_)) for a_, tf_, e_ in out["skipped"]],
                                         columns=[t("col_asset"), t("col_tf"), t("col_reason")])
                else:
                    sk_df = pd.DataFrame([(asset_label(a_), fmt_err(e_)) for a_, _tf, e_ in out["skipped"]],
                                         columns=[t("col_asset"), t("col_reason")])
                st.dataframe(sk_df, hide_index=True, **WIDE)

elif app_mode == "terminal":

    with st.sidebar:
        st.markdown("---")
        st.markdown(f"### {t('terminal_settings')}")
        asset_name = st.selectbox(t("symbol"), list(ASSET_ROUTER.keys()), key="w_symbol", format_func=asset_label)
        tf_name = st.selectbox(t("timeframe"), list(TF_MAP.keys()), key="w_tf")
        ctx = (asset_name, tf_name, offset_choice, count_weekend, drop_clearing)
        if st.session_state.get("ctx") != ctx:
            if "ctx" in st.session_state:
                reset_points()
            st.session_state.ctx = ctx
        st.markdown("---")
        st.markdown(f"### {t('wave_points')}")
        labels = [t("pt_a"), t("pt_b"), t("pt_c")]
        for i in range(3):
            if i < len(st.session_state.abc_points):
                p = st.session_state.abc_points[i]
                st.success(f"{labels[i]}: {fmt_price(p['y'])}  ({p['t']:%Y-%m-%d %H:%M})")
            else:
                st.info(t("awaiting", label=labels[i]))

        # Point O (Origin/Anchor) — optional 4th point
        if len(st.session_state.abc_points) >= 4:
            p = st.session_state.abc_points[3]
            st.success(f"{t('pt_o')}: {fmt_price(p['y'])}  ({p['t']:%Y-%m-%d %H:%M})")
        elif len(st.session_state.abc_points) == 3:
            st.info(t("awaiting_origin"))

        if st.button(t("clear_points"), **WIDE):
            reset_points()
            st.rerun()

    is_fx = is_fx_asset(ASSET_ROUTER[asset_name])
    df_raw, fetch_err = fetch_smart_data(asset_name, tf_name)
    df_raw = prepare_ohlc(df_raw, tf_name, is_fx, count_weekend, drop_clearing, offset_choice)

    if is_crypto_asset(ASSET_ROUTER[asset_name]) and tf_name in ("MN3", "MN6", "MN24") and 0 < len(df_raw) < MIN_LTF_BARS:
        st.info(t("crypto_hist_note", tf=tf_name, n=len(df_raw)))

    if df_raw.empty:
        refresh_button("refresh_term")
        st.warning(t("no_data"))
        if fetch_err:
            st.caption(t("reason", detail=fmt_err(fetch_err)))
    else:
        if fetch_err:
            st.caption(t("history_partial", detail=fmt_err(fetch_err)))
        df = add_indicators(df_raw)
        df_plot = df.tail(250).copy()
        df_plot["x_idx"] = np.arange(len(df_plot))
        UIP = chart_ui(MOBILE)

        # Абсолютные экстремумы видимого окна никогда не маскируются (v1.70).
        major_high_mask, major_low_mask = enforce_visible_extremes(df_plot)
        df_plot["Major_High"] = major_high_mask
        df_plot["Major_Low"] = major_low_mask

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_plot["x_idx"], open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
            increasing_line_color="#2c3e50", increasing_fillcolor="white", increasing_line_width=1,
            decreasing_line_color="#2c3e50", decreasing_fillcolor="#2c3e50", decreasing_line_width=1, name=t("chart_price"),
        ))

        last_close = float(df_plot["Close"].iloc[-1])
        pfmt = tick_fmt(last_close)
        time_txt = df_plot.index.strftime("%Y-%m-%d %H:%M").to_numpy()

        def marker_trace(mask, kind, price_col, offset_mult, size, color, name, group):
            """Трейс фракталов: имя сохраняется для ховера и клика, в легенду не выходит."""
            m = np.asarray(mask, dtype=bool)
            sub = df_plot.loc[m]
            sign = 1 if kind == "High" else -1
            return go.Scatter(
                x=sub["x_idx"], y=sub[price_col] + sign * sub["ATR"] * offset_mult,
                mode="markers", marker=dict(size=size, color=color), name=name,
                legendgroup=group, showlegend=False,
                customdata=sub[price_col].to_numpy(dtype=float), text=time_txt[np.flatnonzero(m)],
                hovertemplate=f"{name}<br>{t('hover_' + kind.lower())}: %{{customdata:{pfmt}}}<br>%{{text}}<extra></extra>",
            )

        minor_high = df_plot["Minor_High"].to_numpy(dtype=bool) & ~major_high_mask
        minor_low = df_plot["Minor_Low"].to_numpy(dtype=bool) & ~major_low_mask
        fig.add_trace(marker_trace(minor_high, "High", "High", 0.2, UIP["mark_minor"], MINOR_COLOR, t("chart_minor_high"), "minor"))
        fig.add_trace(marker_trace(minor_low, "Low", "Low", 0.2, UIP["mark_minor"], MINOR_COLOR, t("chart_minor_low"), "minor"))
        fig.add_trace(marker_trace(major_high_mask, "High", "High", 0.5, UIP["mark_major"], MAJOR_COLOR, t("chart_major_high"), "major"))
        fig.add_trace(marker_trace(major_low_mask, "Low", "Low", 0.5, UIP["mark_major"], MAJOR_COLOR, t("chart_major_low"), "major"))

        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=UIP["mark_minor"], color=MINOR_COLOR),
            name=t("chart_minor_group"), legendgroup="minor", showlegend=True, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=UIP["mark_major"], color=MAJOR_COLOR),
            name=t("chart_major_group"), legendgroup="major", showlegend=True, hoverinfo="skip",
        ))

        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["tenkan"], line=dict(color="#2980b9", width=1.5), name="Tenkan-sen"))
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["kijun"], line=dict(color="#e74c3c", width=2), name="Kijun-sen"))
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["chikou"], line=dict(color="#1e8449", width=1.2), name="Chikou Span"))

        x_cloud = np.arange(len(df_plot)) + 26
        sa, sb = df_plot["raw_senkou_a"].to_numpy(dtype=float), df_plot["raw_senkou_b"].to_numpy(dtype=float)
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", fill="toself", fillcolor="rgba(128,128,128,0.3)", line=dict(width=0), name=t("chart_kumo"), legendgroup="cloud", showlegend=True, hoverinfo="skip"))

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

        pts = []
        for p in st.session_state.abc_points:
            if p["t"] in df_plot.index:
                pts.append({"x": int(df_plot.index.get_loc(p["t"])), "y": p["y"]})

        abc = st.session_state.abc_points
        mode_now = st.session_state.get("entry_mode", "hosoda")
        armed = trigger_plan(df, abc[:3], mode_now, tf_name, is_fx, last_close) if len(abc) >= 3 else None
        cand = candidate_c_extreme(df_plot)

        tt_x, tt_text = [], []
        x_view_right = float(len(df_plot) - 1)
        if len(pts) >= 3:
            A, B, C = pts[:3]
            tg = hosoda_targets(A["y"], B["y"], C["y"])
            V, N, E, NT = tg["V"], tg["N"], tg["E"], tg["NT"]
            colors = {"V": "orange", "N": "green", "E": "red", "NT": "purple"}
            for name, val in {"V": V, "N": N, "E": E, "NT": NT}.items():
                fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text=f"{name} {fmt_price(val)}", annotation_position="right", annotation_font_size=UIP["ann_font"], annotation_font_color=colors[name])
            time_ab, time_ac = abs(B["x"] - A["x"]), abs(C["x"] - A["x"])
            clock = _forecast_clock(df_plot, tf_name, is_fx)
            x_view_right = float(max(len(df_plot) - 1, C["x"] + TIME_AXIS_FORWARD_BARS))

            def vlabel(x, text, color, y):
                fig.add_annotation(
                    x=x, y=y, xref="x", yref="paper", text=text, textangle=-90, showarrow=False,
                    xanchor="center", yanchor="middle", font=dict(size=UIP["vlabel_font"], color=color),
                    bgcolor="rgba(255,255,255,0.75)", borderpad=1,
                )

            def time_line(x_pos, base, color, dash, y_zone, hover_head, opacity=1.0):
                ts_, fc_ = bar_time_at(df_plot, x_pos, tf_name, is_fx, clock)
                fig.add_vline(x=x_pos, line_dash=dash, line_color=color, opacity=opacity)
                vlabel(x_pos, time_target_label(base, ts_, fc_, tf_name, MOBILE), color, y_zone)
                tt_x.append(x_pos)
                tt_text.append(hover_head + f"<br>{ts_:%Y-%m-%d %H:%M}" + (f" ({t('hover_forecast')})" if fc_ else ""))

            for x_pos, nm, n_bars, col in ((C["x"] + time_ab, "AB", time_ab, "blue"),
                                           (C["x"] + time_ac, "AC", time_ac, "teal")):
                time_line(x_pos, f"{nm} {int(n_bars)}", col, "dot", 0.30,
                          t("hover_taiyosuu", name=nm, n=int(n_bars)))
            origin_x = pts[3]["x"] if len(pts) >= 4 else pts[0]["x"]
            for k in KIHON_SUU:
                xk = origin_x + k - 1
                if xk > x_view_right:
                    continue
                time_line(xk, str(k), "#7f8c8d", "dash", 0.78, t("hover_kihon", k=k), opacity=0.35)

            fig.add_trace(go.Scatter(x=[A["x"], B["x"], C["x"]], y=[A["y"], B["y"], C["y"]], mode="lines+markers", line=dict(color="#f39c12", width=2), marker=dict(size=UIP["wave_mark"]), name=t("chart_wave"), hovertemplate=f"%{{y:{pfmt}}}<extra>{t('chart_wave')}</extra>"))

            for letter, P_ in zip(("A", "B", "C"), pts[:3]):
                ya, ys, yanch, _off, _va = polar_anchor(df_plot, P_["x"], P_["y"])
                fig.add_annotation(
                    x=P_["x"], y=ya, text=letter, showarrow=False,
                    yshift=ys, yanchor=yanch,
                    font=dict(size=11, color=WAVE_LABEL_COLOR, family="sans-serif"),
                    bgcolor=LABEL_BG, borderpad=1,
                )

            if len(pts) >= 4:
                O_ = pts[3]
                if O_["x"] != A["x"] or O_["y"] != A["y"]:
                    fig.add_trace(go.Scatter(
                        x=[O_["x"]], y=[O_["y"]], mode="markers",
                        marker=dict(size=7, color=ORIGIN_COLOR, symbol="diamond"),
                        name=t("chart_origin"),
                        customdata=[O_["y"]],
                        hovertemplate=t("origin_hover"),
                        showlegend=False,
                    ))
                    ya, ys, yanch, _off, _va = polar_anchor(df_plot, O_["x"], O_["y"])
                    fig.add_annotation(
                        x=O_["x"], y=ya, text="O", showarrow=False,
                        yshift=ys, yanchor=yanch,
                        font=dict(size=11, color=ORIGIN_COLOR),
                        bgcolor=LABEL_BG, borderpad=1,
                    )

        if tt_x:
            y_top = float(df_plot["High"].max())
            fig.add_trace(go.Scatter(
                x=tt_x, y=[y_top] * len(tt_x), mode="markers", marker=dict(size=16, color="rgba(0,0,0,0)"),
                name=t("chart_time_targets"), showlegend=False, text=tt_text, hovertemplate="%{text}<extra></extra>",
            ))

        if cand:
            fig.add_trace(go.Scatter(
                x=[cand["x"]], y=[cand["y"]], mode="markers",
                marker=dict(size=UIP["mark_minor"], color=CAND_C_COLOR),
                name=cand_trace_name(), showlegend=True,
                customdata=[cand["price"]],
                hovertemplate=t("cand_hover"),
                hoverlabel=dict(bgcolor=CAND_HOVER_BG, bordercolor=CAND_HOVER_BORDER,
                                font=dict(size=11, color=CAND_HOVER_FONT), namelength=0),
            ))

        tick_step = max(1, len(df_plot) // UIP["tick_div"])
        time_fmt = axis_time_fmt(tf_name) if MOBILE else "%Y-%m-%d %H:%M"
        yaxis = dict(side="right", tickformat=tick_fmt(last_close), showgrid=True, gridcolor="#f0f0f0", fixedrange=False)
        xaxis = dict(tickmode="array", tickvals=df_plot["x_idx"].to_numpy()[::tick_step],
                     ticktext=df_plot.index.strftime(time_fmt)[::tick_step], showgrid=True, gridcolor="#f0f0f0",
                     tickangle=UIP["tick_angle"], fixedrange=False)
        if len(pts) >= 3:
            xaxis["range"] = [-0.5, x_view_right + 1.5]
        if UIP["y_font"]:
            yaxis["tickfont"] = UIP["y_font"]
        if UIP["tick_font"]:
            xaxis["tickfont"] = UIP["tick_font"]

        fig.update_layout(
            xaxis_rangeslider_visible=False, height=UIP["height"], template="plotly_white",
            plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            margin=UIP["margin"],
            yaxis=yaxis, xaxis=xaxis,
            hovermode="closest", clickmode="event+select", dragmode="pan",
            font=dict(color="#2c3e50"),
            legend=UIP["legend"],
            modebar=dict(bgcolor="rgba(255,255,255,0.9)", color="#2c3e50", activecolor="#e74c3c"),
        )

        with st.container(key="chart_shell"):
            refresh_button("refresh_term")
            event = st.plotly_chart(
                fig,
                key=f"chart_{st.session_state.chart_ver}",
                on_select="rerun",
                selection_mode=("points", "box", "lasso"),
                config={"scrollZoom": False, "displayModeBar": True, "displaylogo": False,
                        "modeBarButtonsToAdd": ["toggleSpikelines"], "modeBarButtonsToRemove": []},
                theme=None,
                **WIDE,
            )

        # --- Интерактивная статус-пилюля: один тап сбрасывает все точки волны (v1.70) ---
        status_label = points_bar_text(len(abc))
        if st.button(status_label, key="pts_bar_btn", help=t("pts_reset_tip"), **WIDE):
            reset_points()
            st.rerun()

        if len(abc) >= 3 and len(pts) < 3:
            st.caption(t("points_outside"))

        _htf_memo = {}

        def htf_info():
            if "v" not in _htf_memo:
                htf_tf = htf_for(asset_name, tf_name)
                if htf_tf == tf_name:
                    df_h = df_raw
                else:
                    df_h_raw, _htf_err = fetch_smart_data(asset_name, htf_tf)
                    df_h = prepare_ohlc(df_h_raw, htf_tf, is_fx, count_weekend, drop_clearing, offset_choice)
                missing = df_h.empty
                _htf_memo["v"] = (np.zeros(len(df)) if missing else htf_trend_series(df_h, df.index), htf_tf, missing)
            return _htf_memo["v"]

        st.markdown(f"#### {t('ai_title')}")
        ai_light = None
        if len(abc) < 3:
            st.caption(t("ai_hint"))
        elif not SKLEARN_OK:
            st.warning(t("ai_err_sklearn"))
        else:
            htf_arr, _htf_tf, htf_missing = htf_info()
            A_, B_, C_ = abc[:3]
            res = alice_run(df, htf_arr, A_["t"], A_["y"], B_["t"], B_["y"], C_["t"], C_["y"], ALICE_TARGETS)
            if res["status"] != "ok":
                st.info(t("ai_err_" + res["status"], **res.get("kw", {})))
            else:
                ok_targets = []
                for name in ALICE_TARGETS:
                    r = res["targets"][name]
                    if r["status"] != "ok":
                        st.info(t("ai_err_" + r["status"], **r.get("kw", {})))
                        continue
                    light = alice_verdict(r)
                    ok_targets.append((name, r))
                    prefix = f"{name}: " if len(ALICE_TARGETS) > 1 else ""
                    st.markdown(
                        f"{prefix}<span style='color:{ALICE_LIGHT_COLORS[light]}; font-size:1.15rem'>&#9679;</span>"
                        f"&nbsp; {t('ai_light_' + light)}", unsafe_allow_html=True)
                    if ai_light is None:
                        ai_light = light
                if ok_targets:
                    with st.expander(t("ai_details_title")):
                        if htf_missing:
                            st.caption(t("ai_htf_missing"))
                        pc = lambda v: f"{v * 100:.1f}"
                        for name, r in ok_targets:
                            if len(ok_targets) > 1:
                                st.markdown(f"**{t('ai_target_name', target=name)}**")
                            if r["det"]:
                                st.caption(t("ai_det_" + r["det"], target=name))
                            else:
                                st.caption(t("ai_d_probs", pt=pc(r["p_target"]), ps=pc(r["p_stop"]), p0=pc(r["p_timeout"])))
                            rr_txt = f"{r['rr']:.2f}" if r["rr"] is not None else t("ai_na")
                            st.caption(t("ai_d_fair", pf=pc(r["p_fair"]), be=pc(r["be"]), rr=rr_txt))
                            edge_pct = r["edge"] * 100
                            st.caption(t("ai_d_edge", edge="0.0" if abs(edge_pct) < 0.05 else f"{edge_pct:+.1f}",
                                         se=pc(r["se"]), neff=r["n_eff"]))
                            if not r["det"]:
                                auc_txt = f"{r['auc']:.2f}" if r["auc"] is not None else t("ai_na")
                                st.caption(t("ai_stats", n=r["n"], neff=r["n_eff"], ft=pc(r["freq"]["target"]),
                                             fs=pc(r["freq"]["stop"]), f0=pc(r["freq"]["timeout"]), auc=auc_txt))
                            st.caption(t("ai_fractals", a=t("ai_fr_" + r["a_st"]), b=t("ai_fr_" + r["b_st"]),
                                         c=t("ai_fr_" + r["c_st"])))
                            st.caption(t("ai_setup", lag=r["lag"], h=r["h"], hmin=ALICE_HORIZON,
                                         ab=t("ai_cls_" + r["ab"]), cls=t("ai_cls_" + r["cls"])))
                            if r["freq_only"]:
                                st.caption(t("ai_freq_only", k=int(round(r["freq"]["target"] * r["n"])), n=r["n"]))
                            if r["pooled"]:
                                st.caption(t("ai_pooled"))
                            if not r["strict"] and r["cls"] == "minor":
                                st.caption(t("ai_live"))
                            if r["uplift"] is not None:
                                st.caption(t("ai_uplift", v=f"{r['uplift']:+.2f}"))
                            st.caption(t("ai_rel_" + r["reliability"]))
                        st.caption(t("ai_disclaimer"))

        if len(abc) >= 3:
            rA, rB, rC = abc[:3]
            side_buy = rB["y"] > rA["y"]
            r_tg = hosoda_targets(rA["y"], rB["y"], rC["y"])
            target_px = float(r_tg["N"])
            route_r = ASSET_ROUTER[asset_name]
            psize, pkey = point_size(route_r)
            unit = t(pkey)
            pval = pip_value_usd(asset_name, last_close, psize)

            atr_last = float(df["ATR"].iloc[-1])
            atr_c = atr_last if np.isfinite(atr_last) else 0.0
            if rC["t"] in df.index:
                cb = df.loc[rC["t"]]
                if np.isfinite(cb["ATR"]):
                    atr_c = float(cb["ATR"])
            stop_buf = STOP_BUFFER_ATR * atr_c
            stop_c = float(rC["y"]) - stop_buf if side_buy else float(rC["y"]) + stop_buf

            entry_mode = st.selectbox(t("entry_mode"), ["hosoda", "break_b", "market", "custom"],
                                      format_func=lambda k: t("entry_" + k), key="entry_mode")

            plan = armed if entry_mode == mode_now else trigger_plan(df, abc[:3], entry_mode, tf_name, is_fx, last_close)
            entry_px, stop_px, dec, conf_txt, expire_ts, bars_n, level_px = None, stop_c, "market", None, None, 0, None
            atr_show, buf_show, stop_src = atr_c, stop_buf, "c"

            if entry_mode in TRIG_WATCH_BARS:
                if plan is None or not plan.get("ok"):
                    why = (plan or {}).get("why", "ref_missing")
                    st.caption(t("trig_no_cloud") if why == "no_cloud" else t("trig_ref_missing"))
                    dec = "invalid"
                else:
                    dec = plan["dec"]
                    level_px, stop_px = plan["level"], plan["stop"]
                    expire_ts, bars_n = plan["expire"], plan["bars"]
                    atr_show, buf_show, stop_src = plan["atr_now"], plan["buf"], plan["stop_src"]
                    if plan["conf_t"] is not None:
                        conf_txt = f"{plan['conf_t']:%Y-%m-%d %H:%M}"
                    if dec == "expired":
                        st.caption(t("trig_expired_note", bars=bars_n))
                    else:
                        entry_px = plan["entry"]
            elif entry_mode == "market":
                entry_px = last_close
            else:
                st.session_state.setdefault("custom_entry", float(last_close))
                dec_c = price_digits(last_close)
                entry_px = float(st.number_input(t("entry_custom_label"), min_value=0.0,
                                                 step=10.0 ** (-dec_c), format=f"%.{dec_c}f", key="custom_entry"))
                if entry_px <= 0:
                    entry_px = None
                    st.caption(t("entry_custom_hint"))

            risk_dist = abs(entry_px - stop_px) if (entry_px is not None and stop_px is not None) else None
            reward_dist = abs(target_px - entry_px) if entry_px is not None else None
            rr = (reward_dist / risk_dist) if (risk_dist is not None and risk_dist > 0) else None

            risk_rows = []
            if level_px is not None:
                risk_rows.append((t("trig_level"), fmt_price(level_px)))
                risk_rows.append((t("trig_decision"), t("dec_" + dec)))
                if plan and plan.get("ok") and plan["dist_atr"] is not None:
                    risk_rows.append((t("trig_dist"), f"{plan['dist_atr']:.2f} ATR"))
            if entry_px is not None:
                lbl = t("risk_entry_plan") if dec in ("limit", "watch") else t("risk_entry")
                risk_rows.append((lbl, fmt_price(entry_px)))
            if conf_txt:
                risk_rows.append((t("trig_confirm"), conf_txt))
            elif dec == "watch":
                risk_rows.append((t("trig_confirm"), t("trig_confirm_wait")))
            if stop_px is not None:
                if stop_src == "cloud":
                    sl_lbl = t("risk_stop_cloud_buy" if side_buy else "risk_stop_cloud_sell")
                else:
                    sl_lbl = t("risk_stop_buy" if side_buy else "risk_stop_sell")
                risk_rows.append((sl_lbl, fmt_price(stop_px)))
            risk_rows.append((t("risk_target"), fmt_price(target_px)))
            if expire_ts is not None:
                risk_rows.append((t("trig_window"), str(bars_n)))
                risk_rows.append((t("trig_expire"), f"{expire_ts:%Y-%m-%d %H:%M}"))
            if entry_px is not None and risk_dist is not None:
                risk_rows.append((t("risk_risk"), f"{fmt_points(risk_dist, psize)} {unit}"))
                risk_rows.append((t("risk_reward"), f"{fmt_points(reward_dist, psize)} {unit}"))
                risk_rows.append((t("risk_rr"), f"1 : {rr:.2f}" if rr is not None else t("ai_na")))
            accent = ALICE_LIGHT_COLORS["green" if side_buy else "red"]
            head = t("risk_title") + " · " + t("risk_buy" if side_buy else "risk_sell")
            st.markdown(risk_card_html(head, risk_rows, accent), unsafe_allow_html=True)

            if dec == "watch" and level_px is not None:
                st.info(t("risk_wait", dir=t("risk_wait_above" if side_buy else "risk_wait_below"),
                          level=fmt_price(level_px)))

            # --- Депозит: при LIVE-телеметрии авто-привязка к equity (disabled), иначе ручной ввод ---
            if MOBILE:
                risk_pct = st.number_input(t("risk_pct_label"), min_value=0.1, max_value=100.0,
                                           step=RISK_PCT_STEP, format="%.1f", key="risk_pct",
                                           help=t("risk_pct_help"))
                if telemetry_live_flag and telemetry_live_equity is not None:
                    try:
                        st.session_state.account_deposit = float(telemetry_live_equity)
                    except (TypeError, ValueError):
                        pass
                    st.number_input(
                        t("deposit_label"),
                        value=float(telemetry_live_equity),
                        disabled=True,
                        format="%.2f",
                        key="account_deposit",
                        help=t("deposit_help"),
                    )
                    st.caption(t("telemetry_locked"))
                else:
                    deposit = st.number_input(t("deposit_label"), min_value=0.0, max_value=1e9,
                                              step=1000.0, format="%.0f", key="account_deposit",
                                              help=t("deposit_help"))
            else:
                rc1, rc2, _rc3 = st.columns([1, 1, 2])
                with rc1:
                    risk_pct = st.number_input(t("risk_pct_label"), min_value=0.1, max_value=100.0,
                                               step=RISK_PCT_STEP, format="%.1f", key="risk_pct",
                                               help=t("risk_pct_help"))
                with rc2:
                    if telemetry_live_flag and telemetry_live_equity is not None:
                        try:
                            st.session_state.account_deposit = float(telemetry_live_equity)
                        except (TypeError, ValueError):
                            pass
                        st.number_input(
                            t("deposit_label"),
                            value=float(telemetry_live_equity),
                            disabled=True,
                            format="%.2f",
                            key="account_deposit",
                            help=t("deposit_help"),
                        )
                        st.caption(t("telemetry_locked"))
                    else:
                        deposit = st.number_input(t("deposit_label"), min_value=0.0, max_value=1e9,
                                                  step=1000.0, format="%.0f", key="account_deposit",
                                                  help=t("deposit_help"))

            lot_ready = (entry_px is not None and rr is not None and pval > 0.0)
            lots, risk_usd, gain_usd = 0.0, 0.0, 0.0
            if lot_ready:
                deposit_val = float(st.session_state.get("account_deposit", 0.0))
                risk_usd = deposit_val * (risk_pct / 100.0)
                pips_risk = risk_dist / psize
                pips_reward = reward_dist / psize
                loss_per_lot = pips_risk * pval
                raw_lots = (risk_usd / loss_per_lot) if loss_per_lot > 0.0 else 0.0
                lots = float(np.floor(raw_lots / LOT_STEP) * LOT_STEP)
                gain_usd = lots * pips_reward * pval
                st.markdown(
                    "<div class='lot-line'>" + t("lot_line", lots=f"{lots:.2f}",
                                                 risk=fmt_money(lots * loss_per_lot, "USD"),
                                                 gain=fmt_money(gain_usd, "USD")) + "</div>",
                    unsafe_allow_html=True)
            elif entry_px is not None:
                st.caption(t("risk_zero") if rr is None else t("lot_no_value"))

            send_clicked = st.button(t("mt5_exec_btn"), key="mt5_send_order",
                                     disabled=(not lot_ready), **WIDE)
            if not lot_ready and dec not in ("expired", "invalid"):
                st.caption(t("mt5_need_entry"))

            if lot_ready:
                if lots < LOT_STEP:
                    st.caption(t("lot_too_small"))
                st.caption(t("risk_outcome", pct=f"{risk_pct:.1f}", loss=f"{risk_pct:.1f}",
                             gain=f"{risk_pct * rr:.1f}", be=f"{100.0 / (1.0 + rr):.1f}"))
                if not ((stop_px < entry_px < target_px) if side_buy else (target_px < entry_px < stop_px)):
                    st.caption(t("risk_geom_bad"))
            pv_txt = f"{pval:.4f}" if 0.0 < pval < 10.0 else f"{pval:.2f}"
            st.caption(t("risk_units", pv=pv_txt, atr=fmt_dist(atr_show)))
            if entry_mode in TRIG_WATCH_BARS and plan and plan.get("ok"):
                st.caption(t("trig_rule_note", lim=f"{ATR_CHASE_LIMIT:.1f}",
                             atr=fmt_dist(plan["atr_now"]), buf=fmt_dist(buf_show)))

            if send_clicked:
                sym_clean = mt5_symbol(asset_name)
                side_txt = "BUY" if side_buy else "SELL"
                order_id = f"{sym_clean}-{tf_name}-{int(pd.Timestamp.now().timestamp())}"
                dg = price_digits(last_close)
                otype = dec if dec in ("market", "limit", "watch") else "market"
                payload = {
                    "token": _mt5_secret(),
                    "id": order_id,
                    "symbol": sym_clean,
                    "side": side_txt,
                    "tf": tf_name,
                    "order_type": otype,
                    "trigger": round(float(level_px if level_px is not None else entry_px), dg),
                    "entry": round(float(entry_px), dg),
                    "sl": round(float(stop_px), dg),
                    "tp": round(float(target_px), dg),
                    "risk_percent": float(risk_pct),
                    "atr": round(float(atr_show), 8),
                    "comment": "Hosoda N",
                }
                if plan and plan.get("ok"):
                    payload["ref_time"] = f"{plan['ref_t']:%Y-%m-%d %H:%M}"
                if expire_ts is not None:
                    payload["expire"] = f"{expire_ts:%Y-%m-%d %H:%M}"
                confirm_label = t("tg_confirm_btn", sym=sym_clean, side=side_txt, lots=f"{lots:.2f}")
                with st.spinner(t("mt5_sending")):
                    ok, err = send_mt5_order(payload, confirm_label)
                if ok:
                    st.success(t("mt5_sent"))
                    st.caption(t("mt5_sent_id", oid=order_id, sym=sym_clean, side=side_txt,
                                 dec=t("dec_" + dec), lots=f"{lots:.2f}", risk=f"{risk_pct:.2f}"))
                    if otype == "watch":
                        st.caption(t("mt5_after_watch"))
                    elif otype == "limit":
                        st.caption(t("mt5_after_limit"))
                    st.caption(t("mt5_confirm_note"))
                else:
                    st.error(t("mt5_err", detail=err))

        if st.button(t("tg_button"), key="tg_send", **WIDE):
            token, chat_id = _tg_credentials()
            if not token or not chat_id:
                st.error(t("tg_no_secrets"))
            else:
                with st.spinner(t("tg_sending")):
                    tg_pts = [{"x": p_["x"], "y": p_["y"]} for p_ in pts] if len(pts) >= 3 else []
                    tg_abc = st.session_state.abc_points[:3]
                    tg_targets = hosoda_targets(*(p_["y"] for p_ in tg_abc)) if len(tg_abc) == 3 else {}
                    htf_arr_t, htf_tf_t, htf_missing_t = htf_info()
                    trend_key = {1.0: "tg_up", -1.0: "tg_down", 0.0: "tg_flat"}[float(htf_arr_t[-1])] if not htf_missing_t else "tg_na"
                    report = t(
                        "tg_report", symbol=asset_label(asset_name), tf=tf_name, bar=f"{df_plot.index[-1]:%Y-%m-%d %H:%M}",
                        price=fmt_price(last_close), htf=htf_tf_t, trend=t(trend_key),
                        target=fmt_price(tg_targets["N"]) if tg_targets else t("tg_na"),
                        verdict=t("ai_light_" + ai_light) if ai_light else t("tg_na"))
                    png, _engine = render_chart_png(fig, df_plot, tg_pts, tg_targets,
                                                    f"{asset_label(asset_name)} | {tf_name}", tf_name, is_fx, MOBILE)
                    ok, err = send_telegram(token, chat_id, report, png)
                if not ok:
                    st.error(t("tg_err", detail=err))
                elif png is None:
                    st.warning(t("tg_sent_text"))
                else:
                    st.success(t("tg_sent"))

        # --- Event handler: up to 4 points (A, B, C, O) ---
        if (event and event.selection and event.selection.get("points")
                and len(event.selection["points"]) == 1 and len(st.session_state.abc_points) < 4):
            clicked = event.selection["points"][0]
            x_val = clicked.get("x")
            if x_val is not None:
                rows = df_plot.loc[df_plot["x_idx"] == x_val]
                if not rows.empty:
                    row = rows.iloc[0]
                    curve = clicked.get("curve_number", clicked.get("curveNumber"))
                    tname = None
                    if isinstance(curve, (int, np.integer)) and 0 <= int(curve) < len(fig.data):
                        tname = fig.data[int(curve)].name
                    price = None
                    if tname in (t("chart_minor_high"), t("chart_major_high")):
                        price = float(row["High"])
                    elif tname in (t("chart_minor_low"), t("chart_major_low")):
                        price = float(row["Low"])
                    elif tname == cand_trace_name():
                        price = float(row["High"]) if (cand and cand["kind"] == "high") else float(row["Low"])
                    elif tname == t("chart_price"):
                        y_val = clicked.get("y")
                        if y_val is None or abs(float(y_val) - row["High"]) <= abs(float(y_val) - row["Low"]):
                            price = float(row["High"])
                        else:
                            price = float(row["Low"])
                    if price is not None and not any(p["t"] == row.name for p in st.session_state.abc_points):
                        st.session_state.abc_points.append({"t": row.name, "y": price})
                        st.rerun()
        gc.collect()
