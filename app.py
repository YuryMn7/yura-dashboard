"""
Quantitative Analysis Terminal — исправленная версия.

Что исправлено относительно исходного файла:
 1. NameError: ASSETS -> sym из ASSET_ROUTER (is_fx_flag).
 2. Опечатка y_int -> yf_int (месячные данные Yahoo теперь грузятся).
 3. Интервалы Yahoo: "m5" -> "5m" и т.д. (единая таблица YF_MAP).
 4. price больше не может остаться неопределённой при клике по Tenkan/Kijun/Chikou.
 5. "Clear Points" сбрасывает и выделение на графике (key графика меняется).
 6. Голые except заменены: ошибки показываются (ключ API из текста ошибок вырезается).
 7. Радар: правильные минимумы баров (LTF >= 110, HTF >= 80), кэш Yahoo, список пропущенных активов.
 8. Опция "UTC": пятница больше не вырезается целиком.
 9. H2/H4/H8 ресемплятся ПОСЛЕ перевода в серверное время (как в MT5); Auto (EET) учитывает летнее время.
Дополнительно:
 - st.set_page_config вызывается первым;
 - совместимость с новыми версиями Streamlit (width="stretch" вместо use_container_width);
 - точки A-B-C привязаны к времени свечи, а не к номеру (не "плывут" при появлении новой свечи);
 - точки сбрасываются при смене символа / таймфрейма / настроек времени;
 - 6- и 24-месячные свечи выровнены по календарю (Янв/Июл и чётные годы);
 - формат цен радара и оси Y зависит от величины цены.
 - выходные режутся по времени Нью-Йорка (пт 17:00 -> вс 17:00 NY): суббота убрана, воскресный вечер остаётся;
   D1: суббота убрана, воскресенье приклеено к понедельнику; галочка "raw" отключает всю фильтрацию;
 - новая опция сервера "NY close (UTC+2/+3)": переход на летнее время по правилам США (как у многих брокеров);
 - подсказки маркеров High/Low показывают High/Low свечи, а не позицию маркера.
 - Chikou Span: сплошная линия, без выхода за левый край графика.
 - "Drop 23:00 Clearing" по умолчанию выключено (в MT5 час 23:00 есть);
 - подписи Kihon/Taiyosuu компактные: серые числа — Kihon suu, "AB n"/"AC n" — Taiyosuu, подписи целей короче.
 - радар использует тот же конвейер prepare_ohlc, что и терминал (выходные по NY, серверное время, клиринг,
   ресемплинг H2/H4/H8 в серверном времени); настройки данных вынесены в общий блок сайдбара.
 - D1 собирается из ЧАСОВЫХ свечей тем же конвейером, что H4 (выходные по NY -> серверное время -> день по серверной
   полуночи): нет лишней «понедельничной» свечи в воскресенье, границы дня как в MT5. Терминал грузит до 3 страниц
   по 5000 часовых свечей (старые страницы кэшируются на 6 часов). W1/MN1 по-прежнему берутся у провайдера.
 - радар: сигналы и тренд — строгие геометрические символы (▲ ▼ ◆) вместо цветных эмодзи; пояснительная строка под
   выбором таймфрейма убрана.
 - переключатель языка English / Русский (первый элемент боковой панели); язык по умолчанию — DEFAULT_LANG;
   все тексты интерфейса лежат в словаре I18N; результаты радара сохраняются при смене языка.
"""
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
    "D1": ("1h", "700d"), "W1": ("1wk", "15y"),   # D1 собирается из часовых (см. BASE_TF)
    "MN1": ("1mo", "max"), "MN6": ("1mo", "max"), "MN24": ("1mo", "max"),
}

# Таймфреймы, которые собираются ресемплингом из базового
BASE_TF = {"H2": "H1", "H4": "H1", "H8": "H1", "D1": "H1", "MN6": "MN1", "MN24": "MN1"}
RESAMPLE_RULE = {"H2": "2h", "H4": "4h", "H8": "8h", "D1": "1D", "MN6": "6MS", "MN24": "24MS"}

# Twelve Data отдаёт не больше 5000 свечей за запрос. Для D1 (из часовых) нужна история глубже -> несколько страниц.
TD_PAGE_SIZE = 5000
TD_PAGES = {"D1": 3}  # 3 x 5000 часовых свечей ~ 450+ торговых дней

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
# ПЕРЕВОДЫ (English / Русский)
# ==========================================
LANGS = {"English": "en", "Русский": "ru"}
DEFAULT_LANG = "Русский"  # язык по умолчанию: "English" или "Русский"
LANG = LANGS[DEFAULT_LANG]

I18N = {
    "en": {
        "nav": "Navigation",
        "module": "Select Module:",
        "mode_radar": "Market Scanner (Radar)",
        "mode_terminal": "Analytical Terminal",
        "data_settings": "Data Settings (Radar + Terminal)",
        "server_time": "Server Time (MT5):",
        "raw": "Include Saturday & closing night (raw)",
        "raw_help": "Off: Saturday and closed hours (Fri 17:00 NY - Sun 17:00 NY) are removed, Sunday evening is kept. "
                    "On: raw provider data with no filtering at all.",
        "clearing": "Drop 23:00 Clearing",
        "clearing_help": "Removes the 23:00 server-time hour (it exists in MT5). Off by default.",
        "terminal_settings": "Terminal Settings",
        "symbol": "Symbol:",
        "timeframe": "Timeframe:",
        "wave_points": "Wave Points (A-B-C)",
        "pt_a": "A (Start)",
        "pt_b": "B (Peak/Trough)",
        "pt_c": "C (Retracement)",
        "awaiting": "Awaiting {label}...",
        "clear_points": "Clear Points",
        "scanner_title": "Global Market Scanner",
        "select_tf": "Select Timeframe:",
        "run_scan": "Execute Market Scan",
        "scanning": "Scanning market data...",
        "processing": "Processing {asset}...",
        "col_asset": "Asset",
        "col_signal": "Signal",
        "col_htf": "HTF Trend",
        "col_price": "Price",
        "col_kijun": "Kijun",
        "col_reason": "Reason",
        "trend_up": "▲ UP",
        "trend_down": "▼ DOWN",
        "trend_flat": "◆ FLAT",
        "sig_strong_buy": "▲▲ STRONG BUY (HTF Confirmed)",
        "sig_local_buy": "▲ Local BUY",
        "sig_strong_sell": "▼▼ STRONG SELL (HTF Confirmed)",
        "sig_local_sell": "▼ Local SELL",
        "no_setups": "Scan completed. No valid entry setups found near Kijun-sen.",
        "skipped": "Skipped assets ({n})",
        "stale_scan": "These results are from an earlier scan (the timeframe or data settings have changed since). "
                      "Run the scan again to refresh them.",
        "no_data": "Market data is currently unavailable.",
        "reason": "Reason: {detail}",
        "points_outside": "Some A-B-C points are outside the visible 250 candles - press Clear Points or change the timeframe.",
        "chart_price": "Price",
        "chart_kumo": "Kumo Cloud",
        "chart_minor_high": "Minor High",
        "chart_minor_low": "Minor Low",
        "chart_major_high": "Major High",
        "chart_major_low": "Major Low",
        "hover_high": "High",
        "hover_low": "Low",
        "chart_wave": "Wave A-B-C",
        "err_nodata": "no data",
        "err_yahoo_nodata": "Yahoo: no data for {detail}",
        "err_td": "TwelveData: {detail}",
        "err_td_nodata": "TwelveData: no data",
        "err_exception": "{detail}",
        "err_no_processed": "no data after processing",
        "err_few_bars": "not enough bars (LTF {ltf}/{min_ltf}, HTF {htf}/{min_htf})",
        "err_nan": "indicators not ready (NaN)",
        "history_partial": "Part of the history could not be loaded ({detail}); the chart may be shorter than usual.",
    },
    "ru": {
        "nav": "Навигация",
        "module": "Выберите модуль:",
        "mode_radar": "Сканер рынка (Радар)",
        "mode_terminal": "Аналитический терминал",
        "data_settings": "Настройки данных (Радар + Терминал)",
        "server_time": "Серверное время (MT5):",
        "raw": "Считать субботу и ночь закрытия (сырые данные)",
        "raw_help": "Выкл: суббота и закрытые часы (пт 17:00 NY — вс 17:00 NY) убраны, воскресный вечер остаётся. "
                    "Вкл: сырые данные провайдера без какой-либо фильтрации.",
        "clearing": "Убрать клиринг 23:00",
        "clearing_help": "Вырезает час 23:00 серверного времени (в MT5 этот час есть). По умолчанию выключено.",
        "terminal_settings": "Настройки терминала",
        "symbol": "Инструмент:",
        "timeframe": "Таймфрейм:",
        "wave_points": "Точки волны (A-B-C)",
        "pt_a": "A (начало)",
        "pt_b": "B (пик/впадина)",
        "pt_c": "C (откат)",
        "awaiting": "Ожидается {label}...",
        "clear_points": "Сбросить точки",
        "scanner_title": "Глобальный сканер рынка",
        "select_tf": "Выберите таймфрейм:",
        "run_scan": "Запустить сканирование",
        "scanning": "Сканирование рынка...",
        "processing": "Обработка: {asset}...",
        "col_asset": "Актив",
        "col_signal": "Сигнал",
        "col_htf": "Старший тренд",
        "col_price": "Цена",
        "col_kijun": "Киджун",
        "col_reason": "Причина",
        "trend_up": "▲ ВВЕРХ",
        "trend_down": "▼ ВНИЗ",
        "trend_flat": "◆ ФЛЭТ",
        "sig_strong_buy": "▲▲ СИЛЬНАЯ ПОКУПКА (старший ТФ подтверждает)",
        "sig_local_buy": "▲ Локальная ПОКУПКА",
        "sig_strong_sell": "▼▼ СИЛЬНАЯ ПРОДАЖА (старший ТФ подтверждает)",
        "sig_local_sell": "▼ Локальная ПРОДАЖА",
        "no_setups": "Сканирование завершено. Подходящих точек входа у Киджун-сен не найдено.",
        "skipped": "Пропущенные активы ({n})",
        "stale_scan": "Эти результаты получены в предыдущем сканировании (с тех пор изменились таймфрейм или настройки данных). "
                      "Запустите сканирование заново, чтобы обновить их.",
        "no_data": "Рыночные данные сейчас недоступны.",
        "reason": "Причина: {detail}",
        "points_outside": "Часть точек A-B-C вышла за пределы видимых 250 свечей — нажмите «Сбросить точки» или смените таймфрейм.",
        "chart_price": "Цена",
        "chart_kumo": "Облако Кумо",
        "chart_minor_high": "Малый максимум",
        "chart_minor_low": "Малый минимум",
        "chart_major_high": "Главный максимум",
        "chart_major_low": "Главный минимум",
        "hover_high": "Хай",
        "hover_low": "Лоу",
        "chart_wave": "Волна A-B-C",
        "err_nodata": "нет данных",
        "err_yahoo_nodata": "Yahoo: нет данных для {detail}",
        "err_td": "TwelveData: {detail}",
        "err_td_nodata": "TwelveData: нет данных",
        "err_exception": "{detail}",
        "err_no_processed": "нет данных после обработки",
        "err_few_bars": "мало баров (LTF {ltf}/{min_ltf}, HTF {htf}/{min_htf})",
        "err_nan": "индикаторы не готовы (NaN)",
        "history_partial": "Часть истории не загрузилась ({detail}); график может быть короче обычного.",
    },
}


def t(key, **kw):
    """Строка интерфейса на выбранном языке (если перевода нет — английская)."""
    text = I18N.get(LANG, {}).get(key) or I18N["en"].get(key, key)
    return text.format(**kw) if kw else text


def E(code, **kw):
    """Языконезависимая ошибка: (код, параметры). Текст строится при показе (fmt_err)."""
    return (code, kw)


def fmt_err(err):
    if isinstance(err, tuple):
        return t("err_" + err[0], **err[1])
    return str(err)



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


def is_fx_asset(route):
    """Форекс и золото (символы с "/", кроме BTC): к ним применяется фильтр выходных."""
    sym = route["sym"]
    return ("/" in sym) and ("BTC" not in sym)


def prepare_ohlc(df_utc, tf, is_fx, raw, drop_clearing, server_choice):
    """ЕДИНЫЙ конвейер для терминала и радара: UTC-данные провайдера -> свечи как в MT5.
    raw=True — никакой фильтрации (сырые данные провайдера)."""
    if df_utc.empty:
        return df_utc
    filter_on = is_fx and not raw
    df = df_utc.copy()
    if tf in ("W1", "MN1", "MN6", "MN24"):
        df.index = df.index.tz_localize(None)
        if tf in RESAMPLE_RULE:
            df = resample_ohlc(df, RESAMPLE_RULE[tf])
    else:
        # внутридневные и D1 (D1 собирается из часовых): выходные (по NY) -> серверное время -> клиринг
        # -> ресемплинг (H2/H4/H8/D1: день режется по серверной полуночи, как в MT5)
        if filter_on:
            df = drop_weekend_ny(df)
        if not df.empty:
            df = to_server_time(df, server_choice)
            if filter_on and drop_clearing:
                df = drop_clearing_hour(df, server_choice)
            if tf in RESAMPLE_RULE:
                df = resample_ohlc(df, RESAMPLE_RULE[tf])
            if tf == "D1" and filter_on:
                df = glue_sunday(df)  # редкий случай: воскресный вечер попал на воскресенье сервера -> к понедельнику
    if not df.empty:
        df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


@st.cache_data(ttl=300, show_spinner=False)
def fetch_yahoo(sym, interval):
    """Возвращает (df_utc, error). Данные БЕЗ ресемплинга (базовый ТФ)."""
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
    """Ошибка страницы Twelve Data. Исключения не кэшируются st.cache_data — сбой не «залипает»."""


def _td_request(sym, base_int, end_date=None):
    """Одна страница Twelve Data (до 5000 свечей, UTC). Возвращает (df_utc, error)."""
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
    """Старая страница истории: она не меняется, поэтому кэшируем на 6 часов (ошибки не кэшируются)."""
    df, err = _td_request(sym, base_int, end_date)
    if err:
        raise TDError(err)
    return df


def _next_monday(ts):
    """Ближайший понедельник 00:00 строго позже ts — граница страницы стабильна в течение недели (кэш работает)."""
    d = ts.normalize()
    return d + pd.Timedelta(days=(7 - d.dayofweek) % 7 or 7)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_smart_data(asset_key, interval):
    """Возвращает (df_utc, error). Данные БЕЗ ресемплинга (базовый ТФ).
    error при непустом df означает, что часть истории не загрузилась."""
    route = ASSET_ROUTER[asset_key]
    if route["prov"] == "yahoo":
        return fetch_yahoo(route["yf"], interval)

    base_int = TF_MAP[BASE_TF.get(interval, interval)]
    df, err = _td_request(route["sym"], base_int)
    if err or df.empty:
        return df, err or E("td_nodata")

    frames, page, partial_err = [df], df, None
    for _ in range(TD_PAGES.get(interval, 1) - 1):
        if len(page) < TD_PAGE_SIZE - 100:  # страница неполная -> история закончилась
            break
        end = _next_monday(page.index.min())
        try:
            page = _td_old_page(route["sym"], base_int, end.strftime("%Y-%m-%d %H:%M:%S"))
        except TDError as ex:
            err_t = ex.args[0]
            detail = str(err_t[1].get("detail", "")) if isinstance(err_t, tuple) else ""
            if "no data" not in detail.lower():  # "нет данных" на этих датах = начало истории, не ошибка
                partial_err = err_t
            break
        if page.empty:
            break
        frames.append(page)

    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out, partial_err


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
# Ключи виджетов, значения которых сохраняем при смене языка
# (в старых версиях Streamlit смена подписи виджета сбрасывает его состояние).
PERSIST_KEYS = ["w_mode", "w_server", "w_raw", "w_clear", "w_symbol", "w_tf", "w_radar_tf"]


def _on_lang_change():
    st.session_state["_keep"] = {k: st.session_state[k] for k in PERSIST_KEYS if k in st.session_state}


_keep = st.session_state.pop("_keep", None)
if _keep:
    for _k, _v in _keep.items():
        st.session_state[_k] = _v

st.session_state.setdefault("lang", DEFAULT_LANG)
st.session_state.setdefault("w_tf", "H1")
st.session_state.setdefault("w_radar_tf", "D1")

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

# ==========================================
# Вкладка 1: РАДАР
# ==========================================
if app_mode == "radar":
    st.markdown(f"<h2 style='color: #2c3e50;'>{t('scanner_title')}</h2>", unsafe_allow_html=True)
    radar_tf = st.selectbox(
        t("select_tf"),
        ["M15", "M30", "H1", "H2", "H4", "H8", "D1", "W1", "MN1", "MN6", "MN24"],
        key="w_radar_tf",
    )

    def fetch_radar(route, tf):
        """Yahoo (UTC) -> тот же конвейер prepare_ohlc, что и в терминале."""
        df, err = fetch_yahoo(route["yf"], tf)
        if err or df.empty:
            return df, err or E("nodata")
        df = prepare_ohlc(df, tf, is_fx_asset(route), count_weekend, drop_clearing, offset_choice)
        if df.empty:
            return df, E("no_processed")
        return df, None

    if st.button(t("run_scan"), **WIDE):
        my_bar = st.progress(0, text=t("scanning"))
        radar_results, skipped = [], []
        htf_radar = RADAR_HTF_MAP.get(radar_tf, "MN1")

        for i, (asset_name, route) in enumerate(ASSET_ROUTER.items()):
            my_bar.progress((i + 1) / len(ASSET_ROUTER), text=t("processing", asset=asset_name))
            try:
                df_ltf, err_l = fetch_radar(route, radar_tf)
                df_htf, err_h = fetch_radar(route, htf_radar)
                if err_l or err_h:
                    skipped.append((asset_name, err_l or err_h))
                    continue
                if len(df_ltf) < MIN_LTF_BARS or len(df_htf) < MIN_HTF_BARS:
                    skipped.append((asset_name, E(
                        "few_bars", ltf=len(df_ltf), min_ltf=MIN_LTF_BARS, htf=len(df_htf), min_htf=MIN_HTF_BARS
                    )))
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
                    skipped.append((asset_name, E("nan")))
                    continue

                # --- СТАРШИЙ ТРЕНД ---
                h_kumo_top = max(h_v["senkou_a"], h_v["senkou_b"])
                h_kumo_bot = min(h_v["senkou_a"], h_v["senkou_b"])
                htf_bullish = h_v["Close"] > h_kumo_top and h_v["tenkan"] >= h_v["kijun"]
                htf_bearish = h_v["Close"] < h_kumo_bot and h_v["tenkan"] <= h_v["kijun"]
                trend_code = "up" if htf_bullish else ("down" if htf_bearish else "flat")

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

                # --- СИГНАЛ (код, текст подставляется при показе на выбранном языке) ---
                sig = None
                if near_kijun:
                    if bullish:
                        sig = "strong_buy" if htf_bullish else "local_buy"
                    elif bearish:
                        sig = "strong_sell" if htf_bearish else "local_sell"

                if sig:
                    radar_results.append({
                        "asset": asset_name, "sig": sig, "trend": trend_code,
                        "price": fmt_price(pr), "kijun": fmt_price(kijun),
                    })
            except Exception as e:
                skipped.append((asset_name, E("exception", detail=safe_err(e))))

        my_bar.empty()
        # результаты хранятся в session_state — не пропадают при смене языка
        st.session_state["radar_out"] = {
            "ctx": (radar_tf, offset_choice, count_weekend, drop_clearing),
            "results": radar_results,
            "skipped": skipped,
        }

    out = st.session_state.get("radar_out")
    if out:
        if out["ctx"] != (radar_tf, offset_choice, count_weekend, drop_clearing):
            st.caption(t("stale_scan"))
        if out["results"]:
            rows_df = pd.DataFrame([
                {
                    t("col_asset"): r["asset"],
                    t("col_signal"): t("sig_" + r["sig"]),
                    t("col_htf"): t("trend_" + r["trend"]),
                    t("col_price"): r["price"],
                    t("col_kijun"): r["kijun"],
                }
                for r in out["results"]
            ])
            st.dataframe(rows_df, hide_index=True, **WIDE)
        else:
            st.info(t("no_setups"))

        if out["skipped"]:
            with st.expander(t("skipped", n=len(out["skipped"]))):
                st.dataframe(
                    pd.DataFrame([(a_, fmt_err(e_)) for a_, e_ in out["skipped"]],
                                 columns=[t("col_asset"), t("col_reason")]),
                    hide_index=True, **WIDE,
                )

# ==========================================
# Вкладка 2: ТЕРМИНАЛ
# ==========================================
elif app_mode == "terminal":

    with st.sidebar:
        st.markdown("---")
        st.markdown(f"### {t('terminal_settings')}")
        asset_name = st.selectbox(t("symbol"), list(ASSET_ROUTER.keys()), key="w_symbol")
        tf_name = st.selectbox(t("timeframe"), list(TF_MAP.keys()), key="w_tf")

        # смена символа/ТФ/настроек времени -> старые точки теряют смысл
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
        if st.button(t("clear_points"), **WIDE):
            reset_points()
            st.rerun()

    df_raw, fetch_err = fetch_smart_data(asset_name, tf_name)
    df_raw = prepare_ohlc(
        df_raw, tf_name, is_fx_asset(ASSET_ROUTER[asset_name]), count_weekend, drop_clearing, offset_choice
    )

    if df_raw.empty:
        st.warning(t("no_data"))
        if fetch_err:
            st.caption(t("reason", detail=fmt_err(fetch_err)))
    else:
        if fetch_err:  # данные есть, но часть истории не загрузилась
            st.caption(t("history_partial", detail=fmt_err(fetch_err)))
        df = add_indicators(df_raw)
        df_plot = df.tail(250).copy()
        df_plot["x_idx"] = np.arange(len(df_plot))

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_plot["x_idx"], open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
            increasing_line_color="#2c3e50", increasing_fillcolor="white", increasing_line_width=1,
            decreasing_line_color="#2c3e50", decreasing_fillcolor="#2c3e50", decreasing_line_width=1, name=t("chart_price"),
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
                hovertemplate=f"{name}<br>{t('hover_' + kind.lower())}: %{{customdata:{pfmt}}}<br>%{{text}}<extra></extra>",
            )

        minor_high = df_plot["Minor_High"] & ~df_plot["Major_High"]
        minor_low = df_plot["Minor_Low"] & ~df_plot["Major_Low"]
        major_high = df_plot["Major_High"]
        major_low = df_plot["Major_Low"]
        fig.add_trace(marker_trace(minor_high, "High", "High", 0.2, 5, "#95a5a6", t("chart_minor_high")))   # 1
        fig.add_trace(marker_trace(minor_low, "Low", "Low", 0.2, 5, "#95a5a6", t("chart_minor_low")))       # 2
        fig.add_trace(marker_trace(major_high, "High", "High", 0.5, 10, "#2c3e50", t("chart_major_high")))  # 3
        fig.add_trace(marker_trace(major_low, "Low", "Low", 0.5, 10, "#2c3e50", t("chart_major_low")))      # 4

        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["tenkan"], line=dict(color="#2980b9", width=1.5), name="Tenkan-sen"))  # 5
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["kijun"], line=dict(color="#e74c3c", width=2), name="Kijun-sen"))  # 6
        # Chikou = Close, сдвинутый на 26 баров НАЗАД (Close[t+26] рисуется на баре t) — как в MT5.
        # Берём готовую колонку chikou (посчитана по всей истории): линия начинается с первой видимой свечи
        # (не вылезает за левый край) и заканчивается за 26 баров до правого края. Линия сплошная.
        fig.add_trace(go.Scatter(x=df_plot["x_idx"], y=df_plot["chikou"], line=dict(color="#1e8449", width=1.2), name="Chikou Span"))  # 7

        x_cloud = np.arange(len(df_plot)) + 26
        sa, sb = df_plot["raw_senkou_a"].to_numpy(dtype=float), df_plot["raw_senkou_b"].to_numpy(dtype=float)

        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", fill="toself", fillcolor="rgba(128,128,128,0.3)", line=dict(width=0), name=t("chart_kumo"), legendgroup="cloud"))

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
                fig.add_hline(y=val, line_dash="dash", line_color=colors[name], annotation_text=f"{name} {fmt_price(val)}", annotation_position="right", annotation_font_size=10, annotation_font_color=colors[name])

            time_ab, time_ac = abs(B["x"] - A["x"]), abs(C["x"] - A["x"])
            def vlabel(x, text, color, y):
                """Компактная вертикальная подпись у верхнего края (y — доля высоты графика)."""
                fig.add_annotation(
                    x=x, y=y, xref="x", yref="paper", text=text, textangle=-90, showarrow=False,
                    xanchor="center", yanchor="middle", font=dict(size=9, color=color),
                    bgcolor="rgba(255,255,255,0.75)", borderpad=1,
                )

            # Taiyosuu: синяя = A-B, бирюзовая = A-C (подпись ниже, чтобы не налезала на Kihon)
            fig.add_vline(x=C["x"] + time_ab, line_dash="dot", line_color="blue")
            vlabel(C["x"] + time_ab, f"AB {int(time_ab)}", "blue", 0.84)
            fig.add_vline(x=C["x"] + time_ac, line_dash="dot", line_color="teal")
            vlabel(C["x"] + time_ac, f"AC {int(time_ac)}", "teal", 0.84)

            for k in KIHON_SUU:
                fig.add_vline(x=C["x"] + k - 1, line_dash="dash", line_color="gray", opacity=0.35)
                vlabel(C["x"] + k - 1, str(k), "#7f8c8d", 0.95)  # серые числа — Kihon suu

            fig.add_trace(go.Scatter(x=[A["x"], B["x"], C["x"]], y=[A["y"], B["y"], C["y"]], mode="lines+markers", line=dict(color="#f39c12", width=2), marker=dict(size=8), name=t("chart_wave"), hovertemplate=f"%{{y:{pfmt}}}<extra>{t('chart_wave')}</extra>"))

        tick_step = max(1, len(df_plot) // 10)
        fig.update_layout(
            xaxis_rangeslider_visible=False, height=750, template="plotly_white",
            plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
            margin=dict(l=20, r=110, t=40, b=120),
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
            st.info(t("points_outside"))

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
