import math

from loguru import logger

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


class BacktestEngine:

    def __init__(
        self,
        initial_capital=100000,
        risk_per_trade=1.0,
        reward_ratio=2.0,
        max_daily_loss=2000,
        max_trades_per_day=5,
        slippage_bps=5
    ):

        self.initial_capital = initial_capital
        self.capital = initial_capital

        self.risk_per_trade = risk_per_trade
        self.reward_ratio = reward_ratio
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        self.slippage_bps = slippage_bps
        self.slippage_rate = slippage_bps / 10_000

        self.position = None
        self.trades = []

        # Equity Curve
        self.equity_curve = [self.initial_capital]

        self.peak_capital = initial_capital
        self.max_drawdown = 0
        self.max_drawdown_percent = 0

        # Daily Risk Controls
        self.daily_trade_count = 0
        self.daily_pnl = 0.0
        self.daily_loss_limit_hit = False

    # ----------------------------------------
    # Daily Risk Control
    # ----------------------------------------

    def can_open_trade(self):

        if self.daily_trade_count >= self.max_trades_per_day:

            logger.warning(
                f"Daily Trade Limit Reached : "
                f"{self.max_trades_per_day}"
            )

            return False

        if self.daily_loss_limit_hit:

            logger.warning(
                "Daily Loss Limit Reached. "
                "New trades blocked."
            )

            return False

        return True

    # ----------------------------------------

    def calculate_quantity(self, entry, stop_loss):

        risk_amount = self.capital * (
            self.risk_per_trade / 100
        )

        risk_per_share = abs(entry - stop_loss)

        if risk_per_share <= 0:
            return 0

        quantity = int(
            risk_amount / risk_per_share
        )

        return max(quantity, 1)

        # ----------------------------------------

    @staticmethod
    def _brokerage_leg(turnover):

        if turnover <= 0:
            return 0.0
        return min(
            BROKERAGE_MAX_PER_ORDER,
            max(BROKERAGE_MIN_PER_ORDER, turnover * BROKERAGE_RATE),
        )

    def calculate_charges(
        self,
        entry,
        exit_price,
        quantity,
        side
    ):
        """Return the verified NSE equity intraday round-trip schedule.

        ``side`` is the position side: BUY means entry BUY/exit SELL;
        SELL means entry SELL/exit BUY. Amounts retain full precision, and
        total charges reconcile to the returned components.
        """
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Unsupported position side: {side}")
        values = (entry, exit_price, quantity)
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("Charge inputs must be finite numbers")
        if float(entry) < 0 or float(exit_price) < 0 or float(quantity) <= 0:
            raise ValueError("Charge inputs must be non-negative")

        entry_turnover = float(entry) * float(quantity)
        exit_turnover = float(exit_price) * float(quantity)
        if side == "BUY":
            buy_turnover = entry_turnover
            sell_turnover = exit_turnover
            entry_brokerage = self._brokerage_leg(buy_turnover)
            exit_brokerage = self._brokerage_leg(sell_turnover)
        else:
            buy_turnover = exit_turnover
            sell_turnover = entry_turnover
            entry_brokerage = self._brokerage_leg(sell_turnover)
            exit_brokerage = self._brokerage_leg(buy_turnover)

        total_turnover = buy_turnover + sell_turnover
        brokerage = entry_brokerage + exit_brokerage
        transaction_charges = total_turnover * NSE_TRANSACTION_RATE
        stt = sell_turnover * STT_SELL_RATE
        stamp_duty = buy_turnover * STAMP_DUTY_BUY_RATE
        sebi_charges = total_turnover * SEBI_RATE
        ipft = total_turnover * IPFT_RATE
        gst = (brokerage + transaction_charges + sebi_charges + ipft) * GST_RATE

        keys = {
            "buy_turnover": buy_turnover,
            "sell_turnover": sell_turnover,
            "entry_brokerage": entry_brokerage,
            "exit_brokerage": exit_brokerage,
            "brokerage": brokerage,
            "transaction_charges": transaction_charges,
            "stt": stt,
            "stamp_duty": stamp_duty,
            "sebi_charges": sebi_charges,
            "ipft": ipft,
            "gst": gst,
        }
        # Keep component precision (including tiny IPFT) and reconcile total
        # exactly to the returned components. Reports may format to paise.
        charge_keys = ("brokerage", "transaction_charges", "stt", "stamp_duty", "sebi_charges", "ipft", "gst")
        keys["total_charges"] = sum(keys[key] for key in charge_keys)
        return keys
    # ----------------------------------------

    # ----------------------------------------
    # Reset Daily Risk Controls
    # ----------------------------------------

    def reset_daily_risk(self):

        self.daily_trade_count = 0
        self.daily_pnl = 0.0
        self.daily_loss_limit_hit = False

        logger.info(
            "Daily Risk Controls Reset"
        )


    def apply_slippage(self, raw_price, transaction_side):

        if transaction_side == "BUY":
            return raw_price * (1 + self.slippage_rate)
        if transaction_side == "SELL":
            return raw_price * (1 - self.slippage_rate)
        raise ValueError(f"Unsupported transaction side: {transaction_side}")

    def execute_entry(
        self,
        side,
        raw_entry_price,
        atr,
        candle_index,
        entry_timestamp=None,
        signal_index=None,
        signal_timestamp=None
    ):

        transaction_side = "BUY" if side == "BUY" else "SELL"
        entry_fill = self.apply_slippage(raw_entry_price, transaction_side)

        if side == "BUY":
            stop_loss = entry_fill - (1.5 * atr)
            target = entry_fill + (2 * atr)
        elif side == "SELL":
            stop_loss = entry_fill + (1.5 * atr)
            target = entry_fill - (2 * atr)
        else:
            raise ValueError(f"Unsupported position side: {side}")

        self.open_trade(
            side=side,
            entry=entry_fill,
            stop_loss=stop_loss,
            target=target,
            candle_index=candle_index,
            entry_timestamp=entry_timestamp,
            raw_entry_price=raw_entry_price,
            signal_index=signal_index,
            signal_timestamp=signal_timestamp,
        )

    def open_trade(
        self,
        side,
        entry,
        stop_loss,
        target,
        candle_index,
        entry_timestamp=None,
        raw_entry_price=None,
        signal_index=None,
        signal_timestamp=None
    ):

        if self.position is not None:
            return

        # Daily Risk Control
        if not self.can_open_trade():
            return

        quantity = self.calculate_quantity(
            entry,
            stop_loss
        )

        if quantity <= 0:
            return

        if raw_entry_price is None:
            raw_entry_price = entry

        self.position = {
            "side": side,
            "entry": entry,
            "raw_entry_price": raw_entry_price,
            "entry_slippage": abs(entry - raw_entry_price),
            "slippage_bps": self.slippage_bps,
            "stop_loss": stop_loss,
            "target": target,
            "quantity": quantity,
            "entry_index": candle_index,
            "entry_timestamp": entry_timestamp,
            "signal_index": signal_index,
            "signal_timestamp": signal_timestamp,
        }

        self.daily_trade_count += 1

        logger.info(
            f"Daily Trade Count : "
            f"{self.daily_trade_count}/{self.max_trades_per_day}"
        )

        logger.info(
            f"BACKTEST {side} | "
            f"Entry={entry:.2f} | "
            f"SL={stop_loss:.2f} | "
            f"Target={target:.2f} | "
            f"Qty={quantity}"
        )
    # ----------------------------------------

    def check_exit(
        self,
        high,
        low,
        candle_index,
        exit_timestamp=None,
        open_price=None
    ):

        if self.position is None:
            return

        trade = self.position
        side = trade["side"]
        stop_loss = trade["stop_loss"]
        target = trade["target"]
        raw_exit_price = None
        reason = None

        # Candle-open gaps are resolved before the intrabar range. If both
        # intrabar levels are touched, the conservative stop-first policy wins.
        if side == "BUY":
            if open_price is not None and open_price <= stop_loss:
                raw_exit_price = open_price
                reason = "STOP_LOSS"
            elif open_price is not None and open_price >= target:
                raw_exit_price = open_price
                reason = "TARGET"
            else:
                stop_touched = low <= stop_loss
                target_touched = high >= target
                if stop_touched:
                    raw_exit_price = stop_loss
                    reason = "STOP_LOSS"
                elif target_touched:
                    raw_exit_price = target
                    reason = "TARGET"
        elif side == "SELL":
            if open_price is not None and open_price >= stop_loss:
                raw_exit_price = open_price
                reason = "STOP_LOSS"
            elif open_price is not None and open_price <= target:
                raw_exit_price = open_price
                reason = "TARGET"
            else:
                stop_touched = high >= stop_loss
                target_touched = low <= target
                if stop_touched:
                    raw_exit_price = stop_loss
                    reason = "STOP_LOSS"
                elif target_touched:
                    raw_exit_price = target
                    reason = "TARGET"

        if raw_exit_price is None:
            return

        transaction_side = "SELL" if side == "BUY" else "BUY"
        exit_fill = self.apply_slippage(raw_exit_price, transaction_side)
        self._close_position(
            exit_price=exit_fill,
            candle_index=candle_index,
            reason=reason,
            exit_timestamp=exit_timestamp,
            raw_exit_price=raw_exit_price,
        )
    
    def _close_position(
        self,
        exit_price,
        candle_index,
        reason,
        exit_timestamp=None,
        raw_exit_price=None
    ):

        if self.position is None:
            return

        trade = self.position
        if raw_exit_price is None:
            raw_exit_price = exit_price
        side = trade["side"]
        entry = trade["entry"]
        quantity = trade["quantity"]

        if side == "BUY":

            pnl = (
                exit_price - entry
            ) * quantity

        else:

            pnl = (
                entry - exit_price
            ) * quantity

        charges = self.calculate_charges(
            entry=entry,
            exit_price=exit_price,
            quantity=quantity,
            side=side
        )

        total_charges = charges["total_charges"]

        net_pnl = pnl - total_charges

        self.capital += net_pnl

        self.daily_pnl += net_pnl

        if self.daily_pnl <= -self.max_daily_loss:
            self.daily_loss_limit_hit = True

        # Record Equity Curve
        self.equity_curve.append(self.capital)

        # Update peak capital and calculate drawdown
        self.peak_capital = max(
            self.peak_capital,
            self.capital
        )

        drawdown = self.peak_capital - self.capital

        drawdown_percent = (
            (drawdown / self.peak_capital) * 100
            if self.peak_capital > 0
            else 0
        )

        self.max_drawdown = max(
            self.max_drawdown,
            drawdown
        )

        self.max_drawdown_percent = max(
            self.max_drawdown_percent,
            drawdown_percent
        )

        result = {
            "side": side,
            "entry": entry,
            "exit": exit_price,
            "raw_entry_price": trade.get("raw_entry_price", entry),
            "entry_fill_price": entry,
            "entry_slippage": trade.get("entry_slippage", 0.0),
            "raw_exit_price": raw_exit_price,
            "exit_fill_price": exit_price,
            "exit_slippage": abs(exit_price - raw_exit_price),
            "slippage_bps": trade.get("slippage_bps", self.slippage_bps),
            "stop_loss": trade["stop_loss"],
            "target": trade["target"],
            "quantity": quantity,

            "gross_pnl": pnl,

            "charges": total_charges,
            "buy_turnover": charges["buy_turnover"],
            "sell_turnover": charges["sell_turnover"],
            "entry_brokerage": charges["entry_brokerage"],
            "exit_brokerage": charges["exit_brokerage"],
            "brokerage": charges["brokerage"],
            "transaction_charges": charges["transaction_charges"],
            "stt": charges["stt"],
            "stamp_duty": charges["stamp_duty"],
            "sebi_charges": charges["sebi_charges"],
            "ipft": charges["ipft"],
            "gst": charges["gst"],

            "pnl": net_pnl,

            "reason": reason,

            "entry_index": trade["entry_index"],
            "exit_index": candle_index,
            "entry_timestamp": trade.get("entry_timestamp"),
            "exit_timestamp": exit_timestamp,
            "signal_index": trade.get("signal_index"),
            "signal_timestamp": trade.get("signal_timestamp")
        }

        self.trades.append(result)

        logger.success(
            f"BACKTEST EXIT | {reason} | "
            f"Entry={entry:.2f} | "
            f"Exit={exit_price:.2f} | "
            f"Qty={quantity} | "
            f"Gross P&L=₹{pnl:.2f} | "
            f"Charges=₹{total_charges:.2f} | "
            f"Net P&L=₹{net_pnl:.2f}"
        )

        self.position = None

    def _close_at_market(
        self,
        raw_exit_price,
        candle_index,
        reason,
        exit_timestamp=None
    ):

        if self.position is None:
            return
        transaction_side = (
            "SELL" if self.position["side"] == "BUY" else "BUY"
        )
        exit_fill = self.apply_slippage(raw_exit_price, transaction_side)
        self._close_position(
            exit_price=exit_fill,
            candle_index=candle_index,
            reason=reason,
            exit_timestamp=exit_timestamp,
            raw_exit_price=raw_exit_price,
        )

    def close_open_position(
        self,
        exit_price,
        candle_index,
        exit_timestamp=None
    ):

        self._close_at_market(
            raw_exit_price=exit_price,
            candle_index=candle_index,
            reason="END_OF_BACKTEST",
            exit_timestamp=exit_timestamp,
        )

    def close_end_of_session(
        self,
        exit_price,
        candle_index,
        exit_timestamp=None
    ):

        self._close_at_market(
            raw_exit_price=exit_price,
            candle_index=candle_index,
            reason="END_OF_SESSION",
            exit_timestamp=exit_timestamp,
        )
    # ----------------------------------------

    def summary(self):

        total_trades = len(self.trades)

        if total_trades == 0:

            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "breakeven_trades": 0,
                "win_rate": 0,
                "gross_profit": 0,
                "gross_loss": 0,
                "profit_factor": 0,
                "average_win": 0,
                "average_loss": 0,
                "net_pnl": 0,
                "final_capital": self.capital
            }

        winning_trades = [
            trade for trade in self.trades
            if trade["pnl"] > 0
        ]

        losing_trades = [
            trade for trade in self.trades
            if trade["pnl"] < 0
        ]

        breakeven_trades = [
            trade for trade in self.trades
            if trade["pnl"] == 0
        ]

        # ----------------------------------------
        # GROSS P&L
        # ----------------------------------------

        gross_profit = sum(
            trade["gross_pnl"]
            for trade in self.trades
            if trade["gross_pnl"] > 0
        )

        gross_loss = abs(sum(
            trade["gross_pnl"]
            for trade in self.trades
            if trade["gross_pnl"] < 0
        ))

        gross_net_pnl = (
            gross_profit - gross_loss
        )

        # ----------------------------------------
        # TOTAL CHARGES
        # ----------------------------------------

        total_charges = sum(
            trade["charges"]
            for trade in self.trades
        )

        # ----------------------------------------
        # NET P&L AFTER CHARGES
        # ----------------------------------------

        net_pnl = (
            gross_net_pnl - total_charges
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0
        )

        average_win = (
            sum(trade["pnl"] for trade in winning_trades)
            / len(winning_trades)
            if winning_trades
            else 0
        )

        average_loss = (
            abs(sum(trade["pnl"] for trade in losing_trades))
            / len(losing_trades)
            if losing_trades
            else 0
        )

        win_rate = (
            len(winning_trades)
            / total_trades
        ) * 100

        logger.info("========================================")
        logger.info("📋 TRADE REPORT")
        logger.info("========================================")

        for index, trade in enumerate(
            self.trades,
            start=1
        ):

            logger.info(
                f"Trade {index} | "
                f"{trade['side']} | "
                f"Entry={trade['entry']:.2f} | "
                f"Exit={trade['exit']:.2f} | "
                f"Qty={trade['quantity']} | "
                f"P&L=₹{trade['pnl']:.2f} | "
                f"Reason={trade['reason']}"
            )

        logger.info("========================================")
        logger.info(
            f"Gross Profit : ₹{gross_profit:.2f}"
        )

        logger.info(
            f"Gross Loss   : ₹{gross_loss:.2f}"
        )

        logger.info(
            f"Gross Net P&L: ₹{gross_net_pnl:.2f}"
        )

        logger.info(
            f"Total Charges: ₹{total_charges:.2f}"
        )

        logger.info(
            f"Profit Factor: {profit_factor:.2f}"
        )

        logger.info(
            f"Average Net Win  : ₹{average_win:.2f}"
        )

        logger.info(
            f"Average Net Loss : ₹{average_loss:.2f}"
        )

        logger.info(
            f"Net P&L       : ₹{net_pnl:.2f}"
        )

        logger.info(
            f"Max Drawdown  : ₹{self.max_drawdown:.2f}"
        )

        logger.info(
            f"Max DD %      : {self.max_drawdown_percent:.2f}%"
        )

        return {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "breakeven_trades": len(breakeven_trades),
            "win_rate": round(win_rate, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "total_charges": round(total_charges, 2),
            "profit_factor": round(profit_factor, 2),
            "average_win": round(average_win, 2),
            "average_loss": round(average_loss, 2),
            "net_pnl": round(net_pnl, 2),
            "gross_net_pnl": round(gross_net_pnl, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_percent": round(
                self.max_drawdown_percent,
                2
            ),
            "final_capital": round(
                self.capital,
                2
            ),

            "equity_curve": self.equity_curve
        }
