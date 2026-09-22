"""Column mapping: UDiFF common bhavcopy format (2024-07-08 onward) -> unified bhav schema.

Verified against a real file: BhavCopy_NSE_CM_0_0_0_20260803_F_0000.csv.zip.
Only equity rows (FinInstrmTp=STK / any SctySrs) matter downstream; the reader keeps all
rows and series filtering happens at query time. TradDt is ISO (YYYY-MM-DD).
Debt/derivative-only columns (StrkPric, OpnIntrst, ...) are not mapped.
"""
COLS = {
    "TradDt": "date",
    "TckrSymb": "symbol",
    "SctySrs": "series",
    "OpnPric": "open",
    "HghPric": "high",
    "LwPric": "low",
    "ClsPric": "close",
    "PrvsClsgPric": "prev_close",
    "LastPric": "last",
    "TtlTradgVol": "volume",
    "TtlTrfVal": "turnover",
    "TtlNbOfTxsExctd": "trades",
    "ISIN": "isin",
}
DATE_FORMATS = (None,)  # ISO; pandas parses it without a format
