"""Column mapping: old bhavcopy format (used until 2024-07-05) -> unified bhav schema.

Verified against real files: cm03JAN2011bhav.csv.zip (no TOTALTRADES/ISIN columns,
trailing empty column) and cm01JAN2024bhav.csv.zip (adds TOTALTRADES, ISIN).
Missing columns are filled as NA by the reader — one mapping covers both variants.
TIMESTAMP format: %d-%b-%Y.
"""
COLS = {
    "SYMBOL": "symbol",
    "SERIES": "series",
    "TIMESTAMP": "date",
    "OPEN": "open",
    "HIGH": "high",
    "LOW": "low",
    "CLOSE": "close",
    "PREVCLOSE": "prev_close",
    "LAST": "last",
    "TOTTRDQTY": "volume",
    "TOTTRDVAL": "turnover",
    "TOTALTRADES": "trades",
    "ISIN": "isin",
}
DATE_FORMATS = ("%d-%b-%Y", "%d-%b-%y")  # COVID-era files (verified: 2020-07) switched to dd-Mon-yy
