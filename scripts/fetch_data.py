import json
import os
from datetime import datetime, timezone, timedelta
import yfinance as yf
import pandas as pd

# 示範成分股清單（可自行擴充完整恒指／港股清單）
SECTORS = {
    "科技": ["0700.HK", "9988.HK", "3690.HK", "1810.HK", "9618.HK", "9888.HK"],
    "金融": ["0005.HK", "1299.HK", "0388.HK", "0939.HK", "1398.HK", "2318.HK"],
    "地產": ["0016.HK", "1113.HK", "0012.HK", "0001.HK", "0823.HK", "0688.HK"],
    "公用事業": ["0002.HK", "0003.HK", "0006.HK", "1038.HK", "0836.HK"],
    "工商業": ["0941.HK", "0883.HK", "0857.HK", "1211.HK", "0669.HK", "2020.HK"],
}

def calc_ma_series(df, window):
    ma = df["Close"].rolling(window).mean()
    return [
        {"time": idx.strftime("%Y-%m-%d"), "value": round(float(val), 2)}
        for idx, val in ma.dropna().items()
    ]

def get_quadrant(ret_5d, ret_20d):
    if ret_20d >= 0 and ret_5d >= 0:
        return "Leading"
    elif ret_20d < 0 and ret_5d >= 0:
        return "Improving"
    elif ret_20d >= 0 and ret_5d < 0:
        return "Weakening"
    return "Lagging"

def main():
    # 1. 抓取恒生指數日線
    hsi = yf.Ticker("^HSI").history(period="2y")
    hsi.index = pd.to_datetime(hsi.index).tz_localize(None)

    candles = [
        {
            "time": idx.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
        }
        for idx, row in hsi.iterrows()
    ]

    latest_close = float(hsi["Close"].iloc[-1])
    prev_close = float(hsi["Close"].iloc[-2])
    chg_pts = round(latest_close - prev_close, 2)
    chg_pct = round((chg_pts / prev_close) * 100, 2)

    # 2. 計算 MA Stability 表（MA20 / MA50 / MA100 / MA200）
    ma_windows = [20, 50, 100, 200]
    ma_table = []
    for w in ma_windows:
        s = hsi["Close"].rolling(w).mean()
        curr_ma = float(s.iloc[-1])
        prev_ma = float(s.iloc[-2])
        diff_pct = ((latest_close - curr_ma) / curr_ma) * 100
        ma_table.append({
            "period": f"MA {w}",
            "value": round(curr_ma, 2),
            "trend": "向上" if curr_ma >= prev_ma else "向下",
            "status": "高於均線" if latest_close >= curr_ma else "跌破均線",
            "diff_pct": round(diff_pct, 2),
        })

    # 3. 計算 HK Breadth 與板塊強弱輪動
    breadth_rows = []
    rotation_rows = []
    all_above = {20: [], 50: [], 100: [], 200: []}

    for sector, tickers in SECTORS.items():
        sec_above = {20: [], 50: [], 100: [], 200: []}
        ret_1d_list, ret_5d_list, ret_20d_list = [], [], []

        for t in tickers:
            try:
                df = yf.Ticker(t).history(period="1y")
                if len(df) < 200:
                    continue
                close = df["Close"]
                c_now = float(close.iloc[-1])
                for w in ma_windows:
                    is_above = 1 if c_now > float(close.rolling(w).mean().iloc[-1]) else 0
                    sec_above[w].append(is_above)
                    all_above[w].append(is_above)

                ret_1d_list.append((c_now / float(close.iloc[-2]) - 1) * 100)
                ret_5d_list.append((c_now / float(close.iloc[-6]) - 1) * 100)
                ret_20d_list.append((c_now / float(close.iloc[-21]) - 1) * 100)
            except Exception:
                continue

        if not sec_above[20]:
            continue

        pct = {w: round(sum(sec_above[w]) / len(sec_above[w]) * 100, 1) for w in ma_windows}
        avg_1d = round(sum(ret_1d_list) / len(ret_1d_list), 2)
        avg_5d = round(sum(ret_5d_list) / len(ret_5d_list), 2)
        avg_20d = round(sum(ret_20d_list) / len(ret_20d_list), 2)

        breadth_rows.append({
            "name": sector,
            "ma20": pct[20],
            "ma50": pct[50],
            "ma100": pct[100],
            "ma200": pct[200],
            "count": len(sec_above[20]),
        })

        rotation_rows.append({
            "name": sector,
            "status": get_quadrant(avg_5d, avg_20d),
            "chg_1d": avg_1d,
            "chg_5d": avg_5d,
            "chg_20d": avg_20d,
        })

    # 加入「大盤總計」至第一列
    if all_above[20]:
        breadth_rows.insert(0, {
            "name": "大盤綜合",
            "ma20": round(sum(all_above[20]) / len(all_above[20]) * 100, 1),
            "ma50": round(sum(all_above[50]) / len(all_above[50]) * 100, 1),
            "ma100": round(sum(all_above[100]) / len(all_above[100]) * 100, 1),
            "ma200": round(sum(all_above[200]) / len(all_above[200]) * 100, 1),
            "count": len(all_above[20]),
        })

    hk_tz = timezone(timedelta(hours=8))
    output = {
        "updated_at": datetime.now(hk_tz).strftime("%Y-%m-%d %H:%M HKT"),
        "hsi": {
            "close": round(latest_close, 2),
            "chg_pts": chg_pts,
            "chg_pct": chg_pct,
            "candles": candles,
            "ma20": calc_ma_series(hsi, 20),
            "ma50": calc_ma_series(hsi, 50),
            "ma200": calc_ma_series(hsi, 200),
        },
        "ma_table": ma_table,
        "breadth": breadth_rows,
        "rotation": rotation_rows,
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
