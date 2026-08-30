import logging
from typing import Any

import ccxt

from freqtrade.enums import CandleType
from freqtrade.exchange import Exchange
from freqtrade.exchange.exchange_types import FtHas
from freqtrade.exchange.exchange_utils_timeframe import timeframe_to_msecs, timeframe_to_seconds
from freqtrade.util import FtTTLCache, dt_ts


logger = logging.getLogger(__name__)

MARKET_OPEN_STATES = ("open", "extended-hours")
MAX_BASE_AGGREGATES = 50000
DAY_IN_SECONDS = 86400
BASE_AGGREGATE_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 60,
    "day": DAY_IN_SECONDS,
    "week": DAY_IN_SECONDS,
    "month": DAY_IN_SECONDS,
    "quarter": DAY_IN_SECONDS,
    "year": DAY_IN_SECONDS,
}


class Massive(Exchange):
    _ccxt_params: dict = {
        "options": {
            "fetchTicker": {"method": "previousDayBar"},
        },
    }

    _ft_has: FtHas = {
        "exchange_has_overrides": {
            "createOrder": True,
            "cancelOrder": True,
            "fetchOrder": True,
            "fetchBalance": True,
        },
        "always_require_api_keys": True,
        "ohlcv_candle_limit": 5000,
        "ohlcv_has_history": True,
        "ohlcv_fill_missing": False,
        "trades_has_history": True,
        "trades_limit": 50000,
        "l2_limit_range": [1],
        "l2_limit_range_required": False,
        "tickers_have_quoteVolume": False,
        "tickers_have_bid_ask": False,
        "tickers_have_percentage": True,
        "tickers_have_price": True,
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._market_status_cache: FtTTLCache = FtTTLCache(maxsize=1, ttl=300)
        self._last_market_open_ts: int = 0

    def ohlcv_candle_limit(
        self, timeframe: str, candle_type: CandleType, since_ms: int | None = None
    ) -> int:
        timespan = str(self._api.timeframes.get(timeframe, "")).partition("/")[2]
        base_seconds = BASE_AGGREGATE_SECONDS.get(timespan)
        timeframe_secs = timeframe_to_seconds(timeframe)
        if not base_seconds or not timeframe_secs:
            return super().ohlcv_candle_limit(timeframe, candle_type, since_ms)
        limit = MAX_BASE_AGGREGATES * base_seconds // timeframe_secs
        return max(1, min(limit, MAX_BASE_AGGREGATES))

    def market_is_open(self) -> bool:
        cached = self._market_status_cache.get("is_open")
        if cached is not None:
            return cached
        try:
            status = self._api.fetch_status()
        except ccxt.BaseError as e:
            logger.warning(
                f"Could not determine market status on {self.name}, assuming open. "
                f"Reason: {e.__class__.__name__} {e}"
            )
            return True
        state = (status.get("info") or {}).get("market")
        is_open = state in MARKET_OPEN_STATES
        self._market_status_cache["is_open"] = is_open
        logger.debug(f"{self.name} market state is {state}.")
        return is_open

    def _now_is_time_to_refresh(self, pair: str, timeframe: str, candle_type: CandleType) -> bool:
        if timeframe_to_seconds(timeframe) >= DAY_IN_SECONDS:
            last_refresh = self._pairs_last_refresh_time.get((pair, timeframe, candle_type), 0)
            if last_refresh + timeframe_to_msecs(timeframe) > dt_ts():
                return False
        elif not super()._now_is_time_to_refresh(pair, timeframe, candle_type):
            return False

        if self.market_is_open():
            self._last_market_open_ts = dt_ts()
            return True
        return dt_ts() - self._last_market_open_ts <= timeframe_to_msecs(timeframe)
