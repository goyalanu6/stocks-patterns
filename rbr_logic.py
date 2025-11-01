import requests
import pandas as pd
import time
from datetime import date
import os
import sys
from typing import Optional, Dict, Any, Tuple

# Import configuration
try:
    from config import (INITIAL_ACCESS_TOKEN, DHAN_CLIENT_ID, API_URL, TOKEN_RENEWAL_URL,
                       EXCHANGE_SEGMENT, INSTRUMENT)
except ImportError:
    print("Error: config.py not found. Please copy config.example.py to config.py and fill in your access token.")
    sys.exit(1)

# Token management
import jwt
from datetime import datetime, timedelta

def is_token_expired(token: str, buffer_minutes: int = 5) -> bool:
    """Check if a token is expired or will expire soon."""
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = decoded.get('exp', 0)
        exp_time = datetime.fromtimestamp(exp_timestamp)
        buffer_time = timedelta(minutes=buffer_minutes)
        return datetime.now() + buffer_time >= exp_time
    except jwt.InvalidTokenError:
        return True

def renew_token(current_token: str, client_id: str) -> str:
    """Attempt to renew the token using the Dhan API."""
    headers = {
        "Content-Type": "application/json",
        "access-token": current_token,
        "dhanClientId": client_id
    }
    
    try:
        resp = requests.post(TOKEN_RENEWAL_URL, headers=headers, json={})
        if resp.status_code == 200:
            new_token = resp.json().get("accessToken")
            if new_token:
                return new_token
        print(f"Token renewal failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Error during token renewal: {e}")
    return current_token

class TokenManager:
    def __init__(self, initial_token: str, client_id: str):
        self._token = initial_token
        self._client_id = client_id
        self._last_renewal = datetime.now()
    
    def get_token(self) -> str:
        """Get a valid token, renewing if necessary."""
        if is_token_expired(self._token):
            self._token = renew_token(self._token, self._client_id)
            self._last_renewal = datetime.now()
        return self._token

# Initialize token manager
_token_manager = TokenManager(INITIAL_ACCESS_TOKEN, DHAN_CLIENT_ID)

def get_current_token() -> str:
    """Get the current access token, renewing if necessary."""
    return _token_manager.get_token()

# Default date settings
FROM_DATE = "2021-01-01"
# Default TO_DATE to today's date in YYYY-MM-DD format
TO_DATE = date.today().isoformat()

def get_headers() -> Dict[str, str]:
    """Get the current headers with a fresh access token."""
    return {
        "Content-Type": "application/json",
        "access-token": get_current_token()
    }

def fetch_for(
    security_id: str,
    from_date: str = FROM_DATE,
    to_date: str = TO_DATE,
    exchange: str = EXCHANGE_SEGMENT,
    instrument: str = INSTRUMENT,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = 10.0,
) -> pd.DataFrame:
    """Fetch historical candles for a single security_id and return a DataFrame.

    This is an explicit top-level function (preferred over returning an inner
    function). The function raises RuntimeError on network / API errors so the
    caller (UI or CLI) can handle or display errors appropriately.

    Example:
        >>> from rbr_logic import fetch_for
        >>> df = fetch_for("21238", from_date="2021-01-01", to_date="2021-12-31")
        >>> df.head()

    Parameters:
      security_id: security identifier as string (used as `securityId` in API)
      from_date / to_date: ISO date strings for the requested range
      exchange / instrument: API parameters (defaults from module config)
      headers: request headers (must include access-token)
      timeout: request timeout in seconds (float)

    Returns:
      pandas.DataFrame with columns [open, high, low, close, timestamp, date]
    """
    payload = {
        "securityId": str(security_id),
        "exchangeSegment": exchange,
        "instrument": instrument,
        "fromDate": from_date,
        "toDate": to_date,
    }

    try:
        resp = requests.post(API_URL, json=payload, headers=headers or get_headers(), timeout=timeout)
    except requests.RequestException as e:
        raise RuntimeError(f"Network error fetching {security_id}: {e}")

    if resp.status_code != 200:
        # raise an error; callers (UI) should catch and display messages
        raise RuntimeError(f"API error {resp.status_code} for {security_id}: {resp.text}")

    data = resp.json()
    df = pd.DataFrame({
        "open": data.get("open", []),
        "high": data.get("high", []),
        "low": data.get("low", []),
        "close": data.get("close", []),
        "timestamp": data.get("timestamp", []),
    })

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    return df

def is_green(c) -> bool:
    return c.close > c.open

def overall(c) -> float:
    return max(c.high - c.low, 1e-9)

def wick_data(c) -> tuple[float, float, float]:
    if is_green(c):
        upper = c.high - c.close
        lower = c.open - c.low
        body = c.close - c.open
    else:
        upper = c.high - c.open
        lower = c.close - c.low
        body = c.open - c.close
    return upper, lower, body

# ---------- Zone detection (only detect zones; no retest here) ----------
def find_demand_zones(df: pd.DataFrame, max_bases: int = 4) -> pd.DataFrame:
    """
    Returns DataFrame with columns:
      date_base, demand_zone_low, demand_zone_high, rally2_idx, num_base_candles
    """
    zones = []
    i = 0
    n = len(df)

    while i < n - 2:
        r1 = df.iloc[i]

        # First strong rally check (green and strong body > 65% of overall)
        if not is_green(r1) or (r1.close - r1.open) / overall(r1) <= 0.65:
            i += 1
            continue

        # Collect 1..4 base candles (strict rule)
        bases = []
        j = i + 1
        while j < n and len(bases) < max_bases:
            c = df.iloc[j]
            upper, lower, body = wick_data(c)
            body_ratio = abs(body) / overall(c)
            wick_ratio = (upper + lower) / overall(c)

            # Base conditions (strict): body <= 35%, wicks >= 65%
            if body_ratio <= 0.35 and wick_ratio >= 0.65:
                bases.append(c)
                j += 1
            else:
                break

        if not bases:
            i += 1
            continue

        # Ensure there's a 2nd rally after bases
        if j >= n:
            break

        r2 = df.iloc[j]
        if not is_green(r2) or (r2.close - r2.open) / overall(r2) <= 0.65:
            i += 1
            continue

        # ✅ demand zone from base range
        body_highs = [(b.close if is_green(b) else b.open) for b in bases]
        lows = [b.low for b in bases]

        dz_high = max(body_highs)
        dz_low = min(lows)
        rally2_idx = j
        zone_height = dz_high - dz_low

        # ✅ date_base = FIRST base candle after rally1
        date_base = bases[0].date

        # ✅ Zone invalidation check (future candles)
        valid_zone = True
        for k in range(rally2_idx + 1, n):
            if df.iloc[k].low < dz_low:  # zone broken
                valid_zone = False
                break

        if not valid_zone:
            i = j + 1
            continue  # ❌ don't include broken zones

        # ✅ If zone valid, store zone info
        zones.append({
            "date_base": date_base,
            "demand_zone_low": float(dz_low),
            "demand_zone_high": float(dz_high),
            "zone_height": float(zone_height),
            "num_base_candles": len(bases),
            "rally2_idx": rally2_idx
        })

        i = j + 1  # skip ahead
    return pd.DataFrame(zones)

def find_retests(df: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    """
    Retest scanning after Rally-2 for demand zone validation.
    
    Rules:
      ✅ Buy when any future candle.low touches demand zone 
         (dz_low <= low <= dz_high)
      ❌ Invalidate when any future candle.low breaks below dz_low
      🕒 Continue scanning until a buy or invalidation occurs
    
    Returns: zones DataFrame with new columns:
      'buy_signal', 'buy_price', 'retest_date', 'invalidated'
    """
    if zones is None or len(zones) == 0:
        return pd.DataFrame(columns=[
            *(zones.columns if zones is not None else []),
            "buy_signal", "buy_price", "retest_date", "invalidated"
        ])

    results = []
    n = len(df)

    for _, zone in zones.iterrows():
        dz_low = float(zone["demand_zone_low"])
        dz_high = float(zone["demand_zone_high"])
        rally2_idx = int(zone["rally2_idx"])

        buy_signal = False
        invalidated = False
        buy_price = None
        retest_date = None

        # ✅ Scan all candles after Rally-2
        for idx in range(rally2_idx + 1, n):
            c = df.iloc[idx]
            low = float(c.low)

            # ❌ Invalidation condition
            if low < dz_low:
                invalidated = True
                break

            # ✅ Buy condition: candle touches within zone
            if dz_low <= low <= dz_high:
                buy_signal = True
                buy_price = low
                retest_date = c.date
                break

        out = zone.to_dict()
        out.update({
            "buy_signal": buy_signal,
            "buy_price": buy_price,
            "retest_date": pd.to_datetime(retest_date) if retest_date else None,
            "invalidated": invalidated
        })

        results.append(out)

    df_out = pd.DataFrame(results)
    return df_out.drop(columns=["zone_height", "rally2_idx"], errors="ignore")

# ---------- Main orchestration ----------
def analyze_security(security_id: str) -> Tuple[Optional[pd.DataFrame], pd.DataFrame]:
    """Fetch and analyze a single security.

    Returns a tuple (df, retests_df) where `df` may be None/empty and
    `retests_df` is a DataFrame (possibly empty).
    """
    df = fetch_for(security_id)
    if df is None or df.empty:
        return None, pd.DataFrame()

    zones = find_demand_zones(df)
    if zones.empty:
        return df, pd.DataFrame()

    retests = find_retests(df, zones)
    print(retests)
    return df, retests


def run_analysis(
    csv_path: Optional[str] = None,
    out_csv: Optional[str] = None,
    sleep_between: float = 0.2,
    max_securities: Optional[int] = 50,
) -> pd.DataFrame:
    """Read CSV, filter required rows, iterate over security IDs and return aggregated DataFrame.

    Parameters:
      csv_path: optional path to api-scrip-master.csv (defaults to script dir)
      out_csv: optional output path to save aggregated results
      sleep_between: pause between API calls
      max_securities: optional int to limit processed securities (for quick runs)
    """
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "api-scrip-master.csv")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at {csv_path}. Put 'api-scrip-master.csv' next to this script or pass csv_path.")

    scrips = pd.read_csv(csv_path, dtype=str)
    required_cols = [
        "SEM_SMST_SECURITY_ID",
        "SEM_EXM_EXCH_ID",
        "SEM_INSTRUMENT_NAME",
        "SEM_SEGMENT",
    ]
    for c in required_cols:
        if c not in scrips.columns:
            raise ValueError(f"Required column '{c}' not found in CSV. Available columns: {list(scrips.columns)}")

    filtered = scrips[
        (scrips["SEM_EXM_EXCH_ID"] == "NSE") &
        (scrips["SEM_INSTRUMENT_NAME"] == "EQUITY") &
        (scrips["SEM_SEGMENT"] == "E")
    ]

    security_ids = filtered["SEM_SMST_SECURITY_ID"].dropna().astype(str).unique().tolist()
    if max_securities is not None:
        security_ids = security_ids[:max_securities]

    all_results = []

    for idx, sid in enumerate(security_ids, start=1):
        # print progress to caller
        print(f"Processing {idx}/{len(security_ids)} securityId={sid} ...")
        try:
            df = fetch_for(sid)
        except Exception as e:
            print(f"Error fetching for {sid}: {e}")
            continue

        if df is None or df.empty:
            print(f"No data for securityId={sid}")
            time.sleep(sleep_between)
            continue

        zones = find_demand_zones(df)
        if zones.empty:
            print(f"No demand zones for {sid}")
            time.sleep(sleep_between)
            continue

        retests = find_retests(df, zones)
        if retests is None or retests.empty:
            print(f"No retests for {sid}")
            time.sleep(sleep_between)
            continue

        for _, r in retests.iterrows():
            out = r.to_dict()
            out["security_id"] = sid
            row_meta = filtered[filtered["SEM_SMST_SECURITY_ID"] == sid]
            if not row_meta.empty:
                first = row_meta.iloc[0]
                out["symbol_name"] = first.get("SEM_SMST_SECURITY_NAME", None) if "SEM_SMST_SECURITY_NAME" in first.index else None
            all_results.append(out)

        time.sleep(sleep_between)

    if not all_results:
        print("No zones detected for any security IDs.")
        return pd.DataFrame()

    final = pd.DataFrame(all_results)
    if "date_base" in final.columns:
        final["date_base"] = pd.to_datetime(final["date_base"], errors="coerce")
    if "retest_date" in final.columns:
        final["retest_date"] = pd.to_datetime(final["retest_date"], errors="coerce")

    if out_csv is None:
        out_csv = os.path.join(os.path.dirname(__file__), "detected_zones_all.csv")

    final.to_csv(out_csv, index=False)
    print(f"Saved aggregated results to {out_csv} (rows={len(final)})")
    return final


if __name__ == "__main__":
    # keep CLI behavior compatible
    final_zones = run_analysis()
    # analyze_security("21238")
