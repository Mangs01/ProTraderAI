import pytest

from backtest.backtest_engine import BacktestEngine
from config.settings import (
    BROKERAGE_MAX_PER_ORDER,
    BROKERAGE_MIN_PER_ORDER,
    BROKERAGE_RATE,
    GST_RATE,
    IPFT_RATE,
    NSE_TRANSACTION_RATE,
    SEBI_RATE,
    STAMP_DUTY_BUY_RATE,
    STT_SELL_RATE,
)


def charges(entry, exit_price, quantity, side):
    return BacktestEngine(slippage_bps=0).calculate_charges(
        entry, exit_price, quantity, side
    )


def test_brokerage_minimum_is_applied_per_leg():
    result = charges(1.0, 2.0, 1, "BUY")
    assert result["entry_brokerage"] == pytest.approx(5.0)
    assert result["exit_brokerage"] == pytest.approx(5.0)
    assert result["brokerage"] == pytest.approx(10.0)


def test_brokerage_percentage_applies_between_floor_and_cap():
    result = charges(100.0, 150.0, 100, "BUY")
    assert result["entry_brokerage"] == pytest.approx(10.0)
    assert result["exit_brokerage"] == pytest.approx(15.0)


def test_brokerage_caps_at_twenty_per_leg():
    result = charges(10_000.0, 20_000.0, 100, "BUY")
    assert result["entry_brokerage"] == pytest.approx(BROKERAGE_MAX_PER_ORDER)
    assert result["exit_brokerage"] == pytest.approx(BROKERAGE_MAX_PER_ORDER)
    assert result["brokerage"] == pytest.approx(40.0)


def test_long_maps_entry_buy_and_exit_sell_directionally():
    entry, exit_price, quantity = 100.0, 110.0, 1_000
    result = charges(entry, exit_price, quantity, "BUY")
    assert result["buy_turnover"] == pytest.approx(entry * quantity)
    assert result["sell_turnover"] == pytest.approx(exit_price * quantity)
    assert result["stt"] == pytest.approx(exit_price * quantity * STT_SELL_RATE)
    assert result["stamp_duty"] == pytest.approx(entry * quantity * STAMP_DUTY_BUY_RATE)


def test_short_maps_entry_sell_and_exit_buy_directionally():
    entry, exit_price, quantity = 100.0, 90.0, 1_000
    result = charges(entry, exit_price, quantity, "SELL")
    assert result["sell_turnover"] == pytest.approx(entry * quantity)
    assert result["buy_turnover"] == pytest.approx(exit_price * quantity)
    assert result["stt"] == pytest.approx(entry * quantity * STT_SELL_RATE)
    assert result["stamp_duty"] == pytest.approx(exit_price * quantity * STAMP_DUTY_BUY_RATE)


def test_turnover_based_rates_apply_to_both_legs():
    result = charges(100.0, 110.0, 1_000, "BUY")
    turnover = 210_000.0
    assert result["transaction_charges"] == pytest.approx(turnover * NSE_TRANSACTION_RATE)
    assert result["sebi_charges"] == pytest.approx(turnover * SEBI_RATE)
    assert result["ipft"] == pytest.approx(turnover * IPFT_RATE)


def test_gst_excludes_stt_and_stamp_duty():
    result = charges(100.0, 110.0, 1_000, "BUY")
    taxable = (
        result["brokerage"]
        + result["transaction_charges"]
        + result["sebi_charges"]
        + result["ipft"]
    )
    assert result["gst"] == pytest.approx(taxable * GST_RATE)
    assert result["gst"] != pytest.approx(
        (taxable + result["stt"] + result["stamp_duty"]) * GST_RATE
    )


def test_total_charge_reconciles_to_all_components():
    result = charges(100.0, 110.0, 1_000, "BUY")
    components = (
        "brokerage", "transaction_charges", "stt", "stamp_duty",
        "sebi_charges", "ipft", "gst",
    )
    assert result["total_charges"] == pytest.approx(
        sum(result[key] for key in components)
    )


def test_long_and_short_directional_tax_bases_differ_correctly():
    long_result = charges(100.0, 110.0, 1_000, "BUY")
    short_result = charges(100.0, 90.0, 1_000, "SELL")
    assert long_result["stt"] == pytest.approx(27.5)
    assert short_result["stt"] == pytest.approx(25.0)
    assert long_result["stamp_duty"] == pytest.approx(3.0)
    assert short_result["stamp_duty"] == pytest.approx(2.7)


def test_trade_record_contains_charge_breakdown_and_accounting_once():
    engine = BacktestEngine(slippage_bps=0)
    engine.open_trade("BUY", 100.0, 90.0, 120.0, 0)
    engine.close_open_position(110.0, 1)
    trade = engine.trades[0]
    components = (
        "brokerage", "transaction_charges", "stt", "stamp_duty",
        "sebi_charges", "ipft", "gst",
    )
    assert all(key in trade for key in components)
    assert trade["charges"] == pytest.approx(
        sum(trade[key] for key in components)
    )
    assert len(engine.trades) == 1
    assert len(engine.equity_curve) == 2


def test_invalid_charge_inputs_are_rejected():
    with pytest.raises(ValueError):
        charges(-1.0, 2.0, 1, "BUY")
    with pytest.raises(ValueError):
        charges(1.0, 2.0, 0, "BUY")