# BIS Effective Exchange Rate (NEER) API

Access BIS Nominal/Real Effective Exchange Rate indices via their SDMX REST API. NEER measures a currency against a weighted basket of all major trading partners — better than bilateral rates for assessing true currency strength.

## API Endpoint

```
GET https://stats.bis.org/api/v1/data/BIS,WS_EER,1.0/{FREQ}.{EER_TYPE}.{EER_BASKET}.{REF_AREA}?format=csv
```

**Dimensions:**
| Dimension | Values | Meaning |
|-----------|--------|---------|
| FREQ | M (monthly), Q (quarterly) | Data frequency |
| EER_TYPE | N (nominal), R (real) | Adjusted for inflation or not |
| EER_BASKET | B (broad, 64 economies), N (narrow, 27) | Basket size |
| REF_AREA | CN, JP, US, etc. | ISO 2-letter country code |

**Working examples:**
```bash
# CNY nominal broad NEER
curl -s "https://stats.bis.org/api/v1/data/BIS,WS_EER,1.0/M.N.B.CN?format=csv" | tail -5

# JPY nominal broad NEER
curl -s "https://stats.bis.org/api/v1/data/BIS,WS_EER,1.0/M.N.B.JP?format=csv" | tail -5

# Multiple countries in one request
curl -s "https://stats.bis.org/api/v1/data/BIS,WS_EER,1.0/M.N.B.CN+JP?format=csv"
```

## CSV Format

```
FREQ,EER_TYPE,EER_BASKET,REF_AREA,UNIT_MEASURE,TIME_FORMAT,COLLECTION,TITLE_TS,TIME_PERIOD,OBS_VALUE,OBS_STATUS,OBS_CONF,OBS_PRE_BREAK
M,N,B,CN,882,,A,China - Nominal - Broad (64 economies),2026-05,111.83,A,F,
```

Key columns:
- Col 8 (`TIME_PERIOD`): `YYYY-MM` format
- Col 9 (`OBS_VALUE`): The index value (base period = 100)
- Col 3 (`REF_AREA`): Country code when fetching multiple

## Nginx Proxy

```nginx
location /fx-bis/ {
    auth_basic off;
    proxy_pass https://stats.bis.org/api/v1/data/BIS,WS_EER,1.0/;
    proxy_ssl_server_name on;
    proxy_set_header Host stats.bis.org;
    proxy_read_timeout 30;  # BIS can be slow
}
```

Frontend usage: `/fx-bis/M.N.B.CN+JP?format=csv`

**⚠ The proxy path already includes the dataflow prefix.** Frontend only needs to append the dimension query.

## Frontend CSV Parser

```js
async function fetchNeer(country) {
  const r = await fetch('/fx-bis/M.N.B.' + country + '?format=csv', {signal: AbortSignal.timeout(15000)});
  const text = await r.text();
  const data = [];
  for (const line of text.trim().split('\n')) {
    const cols = line.split(',');
    if (cols.length >= 10 && cols[9]) {
      const period = cols[8]; // "2026-05"
      const val = parseFloat(cols[9]);
      if (!isNaN(val) && period.match(/^\d{4}-\d{2}$/)) {
        data.push({date: period, value: val});
      }
    }
  }
  return data;
}
```

## Data Freshness

- BIS NEER updates **monthly**, typically with a 1-2 month lag
- As of 2026-06: latest data is May 2026
- Historical data goes back to 1994
- No intraday or daily data — this is a macro indicator

## Interpretation

- Index base = 100 (specific base year varies, typically 2010 or 2020)
- Rising index = currency appreciating against basket
- Falling index = currency depreciating against basket
- CNY NEER 111.83 (May 2026) = ~12% stronger than base period
- JPY NEER 68.73 (May 2026) = ~31% weaker than base period

## Pitfalls

1. **No JSON format** — BIS API returns XML or CSV only. The `format=csv` param works; `format=json` returns 406.
2. **BIS SDMX path syntax is strict** — Must be exactly `data/{dataflow}/{key}`. Extra path segments return error 150.
3. **Country codes are ISO 2-letter** — `CN` not `CNY`, `JP` not `JPY`. The API returns error 100 "No data" for invalid codes.
4. **Excel downloads are stale** — The `.xlsx` files on bis.org are cached snapshots, often months behind the API. Always use the SDMX API for fresh data.
5. **Rate limit** — No documented rate limit, but be polite. One request per page load is fine; don't poll more than hourly.

## Alternative: Real Effective Exchange Rate (CPI-adjusted)

Replace `N` with `R` for CPI-adjusted (real) NEER:
```bash
curl -s "https://stats.bis.org/api/v1/data/BIS,WS_EER,1.0/M.R.B.CN?format=csv" | tail -3
```

Real NEER accounts for inflation differentials — more meaningful for competitiveness analysis but updates with more lag.
