"""Is ETF creation/redemption flow obtainable without paying anyone new?

The nights asked for `fund_flows` more than any other dataset, and it is the
only named mechanism where the forced trader — the authorised participant
creating or redeeming — trades the *same instrument* this project trades. So
it is worth an hour before it is worth a subscription.

The question this answers is narrow and specific. **Does the Tiingo plan we
already pay for return a historical series of shares outstanding or total net
assets?** If it does, flows come free: the daily change in shares outstanding,
times NAV, is the creation/redemption. If it does not, the options are paying a
vendor for history or recording it forward ourselves, and those are different
decisions with different price tags.

Run it on the laptop; the cloud sandbox cannot reach api.tiingo.com.

    python scripts/probe_etf_flows.py

It prints what actually came back rather than what was hoped for, in the same
spirit as the funding parsers: a probe that reports success without showing the
payload is a probe that will be believed when it is wrong.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TICKERS = ("SPY", "HYG", "TLT")
#: Undocumented as far as the search could tell, which is the reason to probe
#: rather than to plan. A 404 here is a finding, not a failure of the script.
ENDPOINTS = (
    "https://api.tiingo.com/tiingo/funds/{t}",
    "https://api.tiingo.com/tiingo/funds/{t}/metrics",
)

#: What we are hunting for, in any spelling a vendor might use.
WANTED = (
    "sharesoutstanding", "shares_outstanding", "sharesout",
    "totalnetassets", "total_net_assets", "netassets", "aum",
    "nav", "flow", "flows",
)


def _get(url: str, token: str) -> tuple[int, object]:
    request = urllib.request.Request(
        url, headers={"Content-Type": "application/json", "Authorization": f"Token {token}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:400]
    except Exception as exc:  # DNS, TLS, timeouts — all the same answer here
        return 0, f"{type(exc).__name__}: {exc}"


def _keys(payload: object) -> list[str]:
    if isinstance(payload, dict):
        return sorted(payload)
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return sorted(payload[0])
    return []


def main() -> int:
    token = os.environ.get("TIINGO_API_KEY")
    if not token:
        print("TIINGO_API_KEY is not set; nothing to probe", file=sys.stderr)
        return 2

    found = False
    for ticker in TICKERS:
        for template in ENDPOINTS:
            url = template.format(t=ticker)
            status, payload = _get(url, token)
            print(f"\n=== {url}\n    HTTP {status}")
            if status != 200:
                print(f"    {payload}")
                continue

            keys = _keys(payload)
            print(f"    keys: {', '.join(keys) or '(not an object or a list of objects)'}")
            hits = [k for k in keys if any(w in k.lower() for w in WANTED)]
            if hits:
                found = True
                print(f"    *** interesting: {', '.join(hits)}")
            rows = payload if isinstance(payload, list) else [payload]
            print(f"    rows: {len(rows)}")
            if rows:
                print(f"    first: {json.dumps(rows[0])[:600]}")
            if len(rows) > 1:
                print(f"    last:  {json.dumps(rows[-1])[:600]}")

    print("\n---")
    if found:
        print(
            "Something with the right shape came back. Next question, and it is the one that\n"
            "decides whether this is usable: is it a HISTORICAL SERIES or a single current\n"
            "value? A current value cannot be backtested — it would tell every past date what\n"
            "is true today, which is the look-ahead that makes a dead idea look alive."
        )
    else:
        print(
            "No shares-outstanding or net-assets field on the plan we already pay for.\n"
            "That leaves two honest options, and they are different decisions:\n"
            "  1. Record it forward ourselves, free, and have a usable history in 6-12 months.\n"
            "  2. Buy history from a vendor (Intrinio, EODHD, ETF Global). Costs money today.\n"
            "Neither is a reason to guess."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
