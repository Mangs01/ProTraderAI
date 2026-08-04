from protection.stop_loss import StopLossManager
from loguru import logger

from execution.order_builder import OrderBuilder
from risk.risk_manager import RiskManager
from position.position_manager import PositionManager
from core.trade_manager import TradeManager
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

    # ----------------------------------------

    def buy(self, entry_price, stop_loss):

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

        logger.success(
            f"BUY ORDER | Qty={quantity}"
        )

        self.stop_loss.set(stop_loss)

        order = OrderBuilder.market_order(

            tradingsymbol=SYMBOL,

            symboltoken=SYMBOL_TOKEN,

            transaction_type="BUY",

            quantity=quantity

        )

        logger.info(order)

        # Live Trading (Future)
        # order_id = self.broker.place_order(order)

    # ----------------------------------------

    def sell(self, entry_price, stop_loss):

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

        logger.warning(
            f"SELL ORDER | Qty={quantity}"
        )

        self.stop_loss.set(stop_loss)

        order = OrderBuilder.market_order(

            tradingsymbol=SYMBOL,

            symboltoken=SYMBOL_TOKEN,

            transaction_type="SELL",

            quantity=quantity

        )

        logger.info(order)

        # Live Trading (Future)
        # order_id = self.broker.place_order(order)

    # ----------------------------------------

    def exit(self):

        if self.trade.is_active():

            self.trade.end_trade()

        if self.position.has_position():

            self.position.close_position()

        self.stop_loss.clear()

        logger.info("EXIT ORDER")