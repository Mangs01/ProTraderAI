from protection import stop_loss
from protection.stop_loss import StopLossManager
from loguru import logger

from execution.order_builder import OrderBuilder
from risk.risk_manager import RiskManager
from position.position_manager import PositionManager
from core.trade_manager import TradeManager

from core.trade_monitor import TradeMonitor
from protection.target_manager import TargetManager
from config.settings import (
    SYMBOL,
    SYMBOL_TOKEN,
    PAPER_BALANCE,
    RISK_PER_TRADE,
    MAX_DAILY_LOSS,
    MAX_TRADE_PER_DAY
)

class OrderManager:

    def __init__(self, broker):

        self.broker = broker

        # Risk Manager
        self.risk = RiskManager(
            capital=PAPER_BALANCE,
            risk_percent=RISK_PER_TRADE,
            max_daily_loss=MAX_DAILY_LOSS,
            max_trade_per_day=MAX_TRADE_PER_DAY
        )

        self.position = PositionManager()
        self.trade = TradeManager()
        self.stop_loss = StopLossManager()
        self.target = TargetManager()

        self.monitor = TradeMonitor(
            trade_manager=self.trade,
            position_manager=self.position,
            stop_loss_manager=self.stop_loss,
            target_manager=self.target
        )

    # ----------------------------------------

    def buy(self, entry_price, stop_loss, target):

        if not self.risk.can_trade():
            logger.warning("Risk Limit Reached")
            return

        if self.trade.is_active():
            logger.warning("Trade Already Active")
            return

        if self.position.has_position():
            logger.warning("Position Already Open")
            return

        quantity = self.risk.position_size(
            entry_price,
            stop_loss
        )

        self.position.open_position(
            side="BUY",
            entry_price=entry_price,
            quantity=quantity
        )

        self.trade.start_trade()

        # Set Stop Loss and Target only once
        self.stop_loss.set(stop_loss, "BUY")
        self.target.set(target, "BUY")

        logger.success(
            f"BUY ORDER | Qty={quantity}"
        )

        order = OrderBuilder.market_order(
            tradingsymbol=SYMBOL,
            symboltoken=SYMBOL_TOKEN,
            transaction_type="BUY",
            quantity=quantity
        )

        logger.info(order)

        return quantity

        # Live Trading (Future)
        # order_id = self.broker.place_order(order)

    # ----------------------------------------

    def sell(self, entry_price, stop_loss, target):

        if not self.risk.can_trade():
            logger.warning("Trading Blocked by Risk Manager")
            return

        if self.trade.is_active():
            logger.warning("Trade Already Active")
            return

        if self.position.has_position():
            logger.warning("Position Already Open")
            return

        quantity = self.risk.position_size(
            entry_price,
            stop_loss
        )

        self.position.open_position(
            side="SELL",
            entry_price=entry_price,
            quantity=quantity
        )

        self.trade.start_trade()

        # Set Stop Loss and Target only once
        self.stop_loss.set(stop_loss, "SELL")
        self.target.set(target, "SELL")

        logger.warning(
            f"SELL ORDER | Qty={quantity}"
        )

        order = OrderBuilder.market_order(
            tradingsymbol=SYMBOL,
            symboltoken=SYMBOL_TOKEN,
            transaction_type="SELL",
            quantity=quantity
        )

        logger.info(order)

        return quantity

        # Live Trading (Future)
        # order_id = self.broker.place_order(order)

    # ----------------------------------------

    def exit(self):

        if self.trade.is_active():
            self.trade.end_trade()

        if self.position.has_position():
            self.position.close_position()

        self.stop_loss.clear()
        self.target.clear()

        logger.info("EXIT ORDER")

    def monitor_trade(self, current_price):

        status = self.monitor.check(current_price)

        if status == "STOP_LOSS":

            logger.warning("Exiting Trade : Stop Loss Hit")
            self.exit()

        elif status == "TARGET":

            logger.success("Exiting Trade : Target Hit")
            self.exit()

        return status