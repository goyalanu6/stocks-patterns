# patterns_logic.py
import pandas as pd
from rbr_logic import fetch_for
from typing import Optional, Tuple

# ------------------------
# Candle helper functions
# ------------------------
def candle_size(c):
    return max(c.high - c.low, 1e-9)

def candle_body(c):
    return abs(c.close - c.open)

def wick_sum(c):
    return (c.high - max(c.open, c.close)) + (min(c.open, c.close) - c.low)

def is_bullish(c):
    return c.close > c.open

def is_bearish(c):
    return c.open > c.close

# ------------------------
# Pattern detection
# ------------------------
def find_pattern(
    df: pd.DataFrame,
    direction: str = "bullish",
    max_bases: int = 4,
    body_threshold: float = 0.65,
    wick_threshold: float = 0.35
) -> pd.DataFrame:
    """
    Detect RBR (bullish), DBD (bearish), RBD (bearish), and DBR (bullish) patterns.

    direction options:
      - "bullish" -> RBR (Rally-Base-Rally)  (demand)
      - "bearish" -> DBD (Drop-Base-Drop)    (supply)
      - "rbd"     -> RBD (Rally-Base-Drop)   (supply)
      - "dbr"     -> DBR (Drop-Base-Rally)   (demand)
    """
    zones = []
    n = len(df)
    i = 0

    while i < n - 2:
        c1 = df.iloc[i]
        size1 = candle_size(c1)
        body1 = candle_body(c1)
        wick1 = wick_sum(c1)

        # ---------- RBR / DBD (existing) ----------
        if direction in ("bullish", "bearish"):
            if direction == "bullish":
                if not is_bullish(c1) or body1 / size1 < body_threshold or wick1 / size1 > wick_threshold:
                    i += 1
                    continue
            else:
                if not is_bearish(c1) or body1 / size1 < body_threshold or wick1 / size1 > wick_threshold:
                    i += 1
                    continue

            bases = []
            j = i + 1
            while j < n and len(bases) < max_bases:
                cb = df.iloc[j]
                s = candle_size(cb)
                b = candle_body(cb)
                w = wick_sum(cb)
                if (b / s) <= wick_threshold and (w / s) >= body_threshold:
                    bases.append(cb)
                    j += 1
                else:
                    break

            if not bases or j >= n:
                i += 1
                continue

            c2 = df.iloc[j]
            size2 = candle_size(c2)
            body2 = candle_body(c2)
            wick2 = wick_sum(c2)

            if direction == "bullish":
                if not is_bullish(c2) or body2 / size2 < body_threshold or wick2 / size2 > wick_threshold:
                    i += 1
                    continue
            else:
                if not is_bearish(c2) or body2 / size2 < body_threshold or wick2 / size2 > wick_threshold:
                    i += 1
                    continue

            if direction == "bullish":
                zone_high = max(max(b.open, b.close) for b in bases)
                zone_low = min(b.low for b in bases)
                pattern_type = "RBR"
            else:
                zone_high = max(b.high for b in bases)
                zone_low = min(min(b.open, b.close) for b in bases)
                pattern_type = "DBD"

            zone_height = abs(zone_high - zone_low)
            date_base = bases[0].date

            zones.append({
                "pattern_type": pattern_type,
                "date_base": date_base,
                "zone_low": float(zone_low),
                "zone_high": float(zone_high),
                "zone_height": float(zone_height),
                "num_base_candles": len(bases),
                "continuation_idx": j
            })

            i = j + 1
            continue

        # ---------- RBD (Rally-Base-Drop) ----------
        if direction == "rbd":
            if not is_bullish(c1) or body1 / size1 < body_threshold or wick1 / size1 > wick_threshold:
                i += 1
                continue

            bases = []
            j = i + 1
            while j < n and len(bases) < max_bases:
                cb = df.iloc[j]
                s = candle_size(cb)
                b = candle_body(cb)
                w = wick_sum(cb)
                if (b / s) <= wick_threshold and (w / s) >= body_threshold:
                    bases.append(cb)
                    j += 1
                else:
                    break

            if not bases or j >= n:
                i += 1
                continue

            c2 = df.iloc[j]
            size2 = candle_size(c2)
            body2 = candle_body(c2)
            wick2 = wick_sum(c2)

            if not is_bearish(c2) or body2 / size2 < body_threshold or wick2 / size2 > wick_threshold:
                i += 1
                continue

            if float(c2.close) >= float(c1.low):
                i += 1
                continue

            zone_high = max(b.high for b in bases)
            zone_low = min(min(b.open, b.close) for b in bases)
            zone_height = abs(zone_high - zone_low)
            date_base = bases[0].date

            zones.append({
                "pattern_type": "RBD",
                "date_base": date_base,
                "zone_low": float(zone_low),
                "zone_high": float(zone_high),
                "zone_height": float(zone_height),
                "num_base_candles": len(bases),
                "continuation_idx": j
            })

            i = j + 1
            continue

        # ---------- DBR (Drop-Base-Rally) - NEW ----------
        if direction == "dbr":
            # first candle: Drop (red)
            if not is_bearish(c1) or body1 / size1 < body_threshold or wick1 / size1 > wick_threshold:
                i += 1
                continue

            # gather base candles
            bases = []
            j = i + 1
            while j < n and len(bases) < max_bases:
                cb = df.iloc[j]
                s = candle_size(cb)
                b = candle_body(cb)
                w = wick_sum(cb)
                if (b / s) <= wick_threshold and (w / s) >= body_threshold:
                    bases.append(cb)
                    j += 1
                else:
                    break

            if not bases or j >= n:
                i += 1
                continue

            # Rally candle
            c2 = df.iloc[j]
            size2 = candle_size(c2)
            body2 = candle_body(c2)
            wick2 = wick_sum(c2)

            if not is_bullish(c2) or body2 / size2 < body_threshold or wick2 / size2 > wick_threshold:
                i += 1
                continue

            # Rally close must be above Drop high
            if float(c2.close) <= float(c1.high):
                i += 1
                continue

            # demand zone
            zone_low = min(b.low for b in bases)
            zone_high = max(max(b.open, b.close) for b in bases)
            zone_height = abs(zone_high - zone_low)
            date_base = bases[0].date

            zones.append({
                "pattern_type": "DBR",
                "date_base": date_base,
                "zone_low": float(zone_low),
                "zone_high": float(zone_high),
                "zone_height": float(zone_height),
                "num_base_candles": len(bases),
                "continuation_idx": j
            })

            i = j + 1
            continue

        i += 1

    return pd.DataFrame(zones)

# ------------------------
# Retests
# ------------------------
def find_retests_rbr(df, zones):
    if zones is None or zones.empty:
        return pd.DataFrame()
    results = []
    n = len(df)
    for _, zone in zones.iterrows():
        low = zone["zone_low"]
        high = zone["zone_high"]
        idx = int(zone["continuation_idx"])
        signal = invalid = False
        price = date = None
        for i in range(idx + 1, n):
            c = df.iloc[i]
            if not signal and low <= c.low <= high:
                signal = True; price = c.low; date = c.date
            if c.low < low: invalid = True; break
        z = zone.to_dict()
        z.update({"buy_signal": signal, "buy_price": price, "retest_date": date, "invalidated": invalid})
        results.append(z)
    return pd.DataFrame(results)

def find_retests_dbd(df, zones):
    if zones is None or zones.empty:
        return pd.DataFrame()
    results = []
    n = len(df)
    for _, zone in zones.iterrows():
        low = zone["zone_low"]
        high = zone["zone_high"]
        idx = int(zone["continuation_idx"])
        signal = invalid = False
        price = date = None
        for i in range(idx + 1, n):
            c = df.iloc[i]
            if not signal and low <= c.high <= high:
                signal = True; price = c.high; date = c.date
            if c.high > high: invalid = True; break
        z = zone.to_dict()
        z.update({"sell_signal": signal, "sell_price": price, "retest_date": date, "invalidated": invalid})
        results.append(z)
    return pd.DataFrame(results)

def find_retests_rbd(df, zones):
    if zones is None or zones.empty:
        return pd.DataFrame()
    results = []
    n = len(df)
    for _, zone in zones.iterrows():
        low = zone["zone_low"]
        high = zone["zone_high"]
        idx = int(zone["continuation_idx"])
        signal = invalid = False
        price = date = None
        for i in range(idx + 1, n):
            c = df.iloc[i]
            if not signal and low <= c.high <= high:
                signal = True; price = c.high; date = c.date
            if c.high > high: invalid = True; break
        z = zone.to_dict()
        z.update({"sell_signal": signal, "sell_price": price, "retest_date": date, "invalidated": invalid})
        results.append(z)
    return pd.DataFrame(results)

def find_retests_dbr(df, zones):
    """
    Retest scanning for DBR (demand zones)
    - Buy when any future candle.low enters the demand zone
    - Invalidate when any candle.low breaks below the demand zone low
    """
    if zones is None or zones.empty:
        return pd.DataFrame()
    results = []
    n = len(df)
    for _, zone in zones.iterrows():
        low = zone["zone_low"]
        high = zone["zone_high"]
        idx = int(zone["continuation_idx"])
        signal = invalid = False
        price = date = None
        for i in range(idx + 1, n):
            c = df.iloc[i]
            if not signal and low <= c.low <= high:
                signal = True; price = c.low; date = c.date
            if c.low < low: invalid = True; break
        z = zone.to_dict()
        z.update({"buy_signal": signal, "buy_price": price, "retest_date": date, "invalidated": invalid})
        results.append(z)
    return pd.DataFrame(results)

# ------------------------
# Entry wrapper
# ------------------------
def analyze_security_patterns(
    security_id: str,
    direction: str,
    body_threshold: float = 0.65,
    wick_threshold: float = 0.35,
    max_bases: int = 4
) -> Tuple[Optional[pd.DataFrame], pd.DataFrame]:
    try:
        df = fetch_for(security_id)
        if df is None or df.empty:
            return None, pd.DataFrame()

        zones = find_pattern(df, direction, max_bases, body_threshold, wick_threshold)
        if zones is None or zones.empty:
            return df, pd.DataFrame()

        if direction == "bullish":
            retests = find_retests_rbr(df, zones)
        elif direction == "bearish":
            retests = find_retests_dbd(df, zones)
        elif direction == "rbd":
            retests = find_retests_rbd(df, zones)
        elif direction == "dbr":
            retests = find_retests_dbr(df, zones)
        else:
            retests = pd.DataFrame()
        return df, retests
    except Exception as e:
        print(f"Error analyzing {security_id}: {e}")
        return None, pd.DataFrame()
