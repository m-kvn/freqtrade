import logging

from freqtrade.exchange import Exchange
from freqtrade.exchange.exchange_types import FtHas


logger = logging.getLogger(__name__)


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
        "trades_has_history": True,
        "trades_limit": 50000,
        "l2_limit_range": [1],
        "l2_limit_range_required": False,
        "tickers_have_quoteVolume": False,
        "tickers_have_bid_ask": False,
        "tickers_have_percentage": True,
        "tickers_have_price": True,
    }
