from unittest.mock import MagicMock

import ccxt
import pytest

from freqtrade.enums import CandleType
from freqtrade.util import dt_ts
from tests.conftest import EXMS, get_patched_exchange


@pytest.mark.parametrize(
    "state,expected",
    [
        ("open", True),
        ("extended-hours", True),
        ("closed", False),
        (None, False),
    ],
)
def test_massive_market_is_open(default_conf, mocker, state, expected):
    api_mock = MagicMock()
    api_mock.fetch_status = MagicMock(return_value={"info": {"market": state}})
    exchange = get_patched_exchange(mocker, default_conf, api_mock, exchange="massive")

    assert exchange.market_is_open() is expected
    assert api_mock.fetch_status.call_count == 1

    assert exchange.market_is_open() is expected
    assert api_mock.fetch_status.call_count == 1


def test_massive_market_is_open_fails_open(default_conf, mocker, caplog):
    api_mock = MagicMock()
    api_mock.fetch_status = MagicMock(side_effect=ccxt.NetworkError("boom"))
    exchange = get_patched_exchange(mocker, default_conf, api_mock, exchange="massive")

    assert exchange.market_is_open() is True
    assert "assuming open" in caplog.text


@pytest.mark.parametrize(
    "state,age_msecs,expected",
    [
        ("open", 0, True),
        ("extended-hours", 0, True),
        ("closed", 0, True),
        ("closed", 2 * 24 * 3600 * 1000, False),
    ],
)
def test_massive_now_is_time_to_refresh(default_conf, mocker, state, age_msecs, expected):
    mocker.patch(f"{EXMS}._now_is_time_to_refresh", return_value=True)
    api_mock = MagicMock()
    api_mock.fetch_status = MagicMock(return_value={"info": {"market": state}})
    exchange = get_patched_exchange(mocker, default_conf, api_mock, exchange="massive")
    exchange._last_market_open_ts = dt_ts() - age_msecs

    assert exchange._now_is_time_to_refresh("AAPL/USD", "1d", CandleType.SPOT) is expected


def test_massive_now_is_time_to_refresh_respects_base(default_conf, mocker):
    mocker.patch(f"{EXMS}._now_is_time_to_refresh", return_value=False)
    api_mock = MagicMock()
    api_mock.fetch_status = MagicMock(return_value={"info": {"market": "open"}})
    exchange = get_patched_exchange(mocker, default_conf, api_mock, exchange="massive")

    assert exchange._now_is_time_to_refresh("AAPL/USD", "1d", CandleType.SPOT) is False
    assert api_mock.fetch_status.call_count == 0


def test_massive_ft_has(default_conf, mocker):
    exchange = get_patched_exchange(mocker, default_conf, exchange="massive")

    assert exchange.get_option("ohlcv_fill_missing") is False
    assert exchange.get_option("always_require_api_keys") is True
    assert exchange.get_option("ohlcv_candle_limit") == 5000
    assert exchange.exchange_has("createOrder") is True
    assert exchange.exchange_has("fetchBalance") is True


@pytest.mark.parametrize("exchange_name,expected_rows", [("massive", 3), ("binance", 5)])
def test_massive_process_ohlcv_df_no_fillup(default_conf, mocker, exchange_name, expected_rows):
    exchange = get_patched_exchange(mocker, default_conf, exchange=exchange_name)
    day = 24 * 3600 * 1000
    start = 1787544000000
    ticks = [
        [start, 1.0, 1.0, 1.0, 1.0, 10.0],
        [start + day, 2.0, 2.0, 2.0, 2.0, 10.0],
        [start + 4 * day, 3.0, 3.0, 3.0, 3.0, 10.0],
    ]

    df = exchange._process_ohlcv_df(
        "AAPL/USD", "1d", CandleType.SPOT, ticks, cache=False, drop_incomplete=False
    )

    assert len(df) == expected_rows
    assert (df["volume"] == 0).sum() == expected_rows - 3
