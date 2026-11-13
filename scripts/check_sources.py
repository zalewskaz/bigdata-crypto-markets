import json
import os
import time
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

import pandas as pd
import requests
import websocket
from dotenv import load_dotenv

load_dotenv()

AV_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
AV_URL = "https://www.alphavantage.co/query"
COINBASE_URL = "https://api.exchange.coinbase.com"
COINBASE_WS = "wss://ws-feed.exchange.coinbase.com"

PAIRS = ["BTC-USD", "ETH-USD"]
SYMBOLS = ["QQQ", "SPY", "GLD"]
START_DATE = "2017-01-01"
WS_SECONDS = 20
DATA_DIR = "data"
USE_SAVED_AV = True

MAX_CANDLES_PER_REQUEST = 300
SECONDS_IN_DAY = 86400
REQUEST_TIMEOUT = 30
COINBASE_PAUSE = 0.3
AV_PAUSE = 1.5
MAX_RETRIES = 3
RETRY_PAUSE = 5

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_rows", 10)


def save(df, name):
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(DATA_DIR + "/" + name, index=False)
    print("zapisano:", DATA_DIR + "/" + name)


def load(name):
    df = pd.read_csv(DATA_DIR + "/" + name)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    print("wczytano:", DATA_DIR + "/" + name)
    return df


def get_json(url, params):
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            return response.json()
        except requests.exceptions.ConnectionError:
            print("błąd połączenia, próba", attempt + 1, "z", MAX_RETRIES)
            time.sleep(RETRY_PAUSE)
    raise Exception("nie udało się połączyć z " + url)


def get_coinbase_daily(pair):
    rows = []
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    today = datetime.utcnow()

    while start < today:
        end = start + timedelta(days=MAX_CANDLES_PER_REQUEST - 1)
        if end > today:
            end = today

        url = COINBASE_URL + "/products/" + pair + "/candles"
        params = {"granularity": SECONDS_IN_DAY, "start": start.isoformat(), "end": end.isoformat()}
        rows = rows + get_json(url, params)

        start = end + timedelta(days=1)
        time.sleep(COINBASE_PAUSE)

    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["date"] = pd.to_datetime(df["time"], unit="s").dt.date
    df["product_id"] = pair
    df = df.drop_duplicates("date")
    df = df.sort_values("date")
    df = df.reset_index(drop=True)
    return df[["product_id", "date", "open", "high", "low", "close", "volume"]]


def get_coinbase_trades(seconds):
    ws = websocket.create_connection(COINBASE_WS, timeout=REQUEST_TIMEOUT)
    subscribe = {"type": "subscribe", "product_ids": PAIRS, "channels": ["matches"]}
    ws.send(json.dumps(subscribe))

    trades = []
    end_time = time.time() + seconds
    while time.time() < end_time:
        message = json.loads(ws.recv())
        if message["type"] == "match":
            trades.append(message)
    ws.close()

    df = pd.DataFrame(trades)
    df = df[["trade_id", "product_id", "price", "size", "side", "sequence", "time"]]
    df["price"] = df["price"].astype(float)
    df["size"] = df["size"].astype(float)
    return df


def get_alpha_vantage(params):
    params["apikey"] = AV_KEY
    data = get_json(AV_URL, params)
    time.sleep(AV_PAUSE)

    if "Information" in data:
        raise Exception("Alpha Vantage: " + data["Information"])
    return data


def get_av_prices(symbol, function, key):
    data = get_alpha_vantage({"function": function, "symbol": symbol})

    df = pd.DataFrame.from_dict(data[key], orient="index")
    df.columns = ["open", "high", "low", "close", "volume"]
    df = df.astype(float)
    df["date"] = pd.to_datetime(df.index).date
    df["symbol"] = symbol

    df = df[df["date"] >= pd.to_datetime(START_DATE).date()]
    df = df.sort_values("date")
    df = df.reset_index(drop=True)
    return df[["symbol", "date", "open", "high", "low", "close", "volume"]]


def get_fed_rate():
    data = get_alpha_vantage({"function": "FEDERAL_FUNDS_RATE", "interval": "daily"})

    df = pd.DataFrame(data["data"])
    df = df[df["value"] != "."]
    df["value"] = df["value"].astype(float)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    df = df[df["date"] >= pd.to_datetime(START_DATE).date()]
    df = df.sort_values("date")
    df = df.reset_index(drop=True)
    return df


def main():
    print("\n1. Coinbase REST - dzienne ceny kryptowalut")
    crypto_daily = {}
    for pair in PAIRS:
        crypto_daily[pair] = get_coinbase_daily(pair)
        print("\n" + pair + ":", len(crypto_daily[pair]), "rekordów")
        print(crypto_daily[pair])
        save(crypto_daily[pair], "coinbase_daily_" + pair + ".csv")

    print("\n2. Coinbase WebSocket - transakcje na żywo przez", WS_SECONDS, "s")
    trades = get_coinbase_trades(WS_SECONDS)
    print("\ntransakcje:", len(trades), "rekordów")
    print(trades)
    print("\nliczba transakcji wg par:")
    print(trades["product_id"].value_counts())
    per_second = len(trades) / WS_SECONDS
    print("szacunek:", round(per_second, 1), "transakcji/s, ok.", int(per_second * SECONDS_IN_DAY), "na dobę")
    save(trades, "coinbase_trades_sample.csv")

    print("\n3. Alpha Vantage - akcje, złoto, stopa Fed")
    if USE_SAVED_AV:
        print("dane z zapisanych plików, bez zapytań do API")

    market_weekly = {}
    market_daily = {}
    for symbol in SYMBOLS:
        if USE_SAVED_AV:
            market_weekly[symbol] = load("av_weekly_" + symbol + ".csv")
            market_daily[symbol] = load("av_daily_" + symbol + ".csv")
        else:
            market_weekly[symbol] = get_av_prices(symbol, "TIME_SERIES_WEEKLY", "Weekly Time Series")
            save(market_weekly[symbol], "av_weekly_" + symbol + ".csv")
            market_daily[symbol] = get_av_prices(symbol, "TIME_SERIES_DAILY", "Time Series (Daily)")
            save(market_daily[symbol], "av_daily_" + symbol + ".csv")

        print("\n" + symbol + " tygodniowo:", len(market_weekly[symbol]), "rekordów")
        print(market_weekly[symbol])
        print("\n" + symbol + " dziennie:", len(market_daily[symbol]), "rekordów")
        print(market_daily[symbol])

    if USE_SAVED_AV:
        fed = load("av_fed_rate.csv")
    else:
        fed = get_fed_rate()
        save(fed, "av_fed_rate.csv")
    print("\nstopa Fed:", len(fed), "rekordów")
    print(fed)

    print("\n4. Czy źródła da się połączyć?")

    weekly = crypto_daily["BTC-USD"].copy()
    weekly["week"] = pd.to_datetime(weekly["date"]).dt.to_period("W")
    weekly = weekly.groupby("week").last().reset_index()
    weekly = weekly[["week", "close"]].rename(columns={"close": "BTC"})
    btc_weeks = len(weekly)

    for symbol in SYMBOLS:
        df = market_weekly[symbol].copy()
        df["week"] = pd.to_datetime(df["date"]).dt.to_period("W")
        df = df[["week", "close"]].rename(columns={"close": symbol})
        weekly = weekly.merge(df, on="week", how="inner")

    print("\nPołączenie tygodniowe (klucz: tydzień):", len(weekly), "wspólnych tygodni z", btc_weeks, "tygodni BTC")
    print(weekly)
    save(weekly, "joined_weekly.csv")

    daily = crypto_daily["BTC-USD"][["date", "close"]].rename(columns={"close": "BTC"})
    for symbol in SYMBOLS:
        df = market_daily[symbol][["date", "close"]].rename(columns={"close": symbol})
        daily = daily.merge(df, on="date", how="left")
    daily = daily.merge(fed.rename(columns={"value": "fed_rate"}), on="date", how="left")
    daily = daily[daily["date"] >= market_daily["SPY"]["date"].min()]

    session_days = daily["SPY"].notna().sum()
    print("\nPołączenie dzienne (klucz: data):", len(daily), "dni, w tym", session_days, "z sesją giełdową i",
          len(daily) - session_days, "bez sesji (weekendy, święta)")
    daily = daily.ffill()
    print(daily)
    save(daily, "joined_daily.csv")

    print("\nWszystkie źródła działają i da się je połączyć.")


if __name__ == "__main__":
    main()
