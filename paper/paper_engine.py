import csv
import os

from datetime import datetime
from loguru import logger


class PaperEngine:

    def __init__(self, starting_balance=100000):

        self.starting_balance = starting_balance
        self.balance = starting_balance

        self.position = None

        self.total_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        self.journal_file = "logs/paper_trades.csv"

        os.makedirs("logs", exist_ok=True)

        self._create_journal()

        logger.info(
            f"Paper Engine Initialized | Balance : ₹{self.balance:.2f}"
        )

    # ----------------------------------------
    # CREATE JOURNAL
    # ----------------------------------------

    def _create_journal(self):

        if os.path.exists(self.journal_file):
            return

        with open(
            self.journal_file,
            mode="w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "date",
                "side",
                "entry",
                "exit",
                "quantity",
                "pnl",
                "reason"
            ])

    # ----------------------------------------
    # BUY
    # ----------------------------------------

    def buy(self, price, quantity=1):

        if self.position is not None:

            logger.warning("Already in Position")

            return False

        self.position = {

            "side": "BUY",

            "entry": float(price),

            "quantity": int(quantity),

            "time": datetime.now()
        }

        logger.success(
            f"PAPER BUY @ {price} | Qty={quantity}"
        )

        return True

    # ----------------------------------------
    # SELL
    # ----------------------------------------

    def sell(self, price, quantity=1):

        if self.position is not None:

            logger.warning("Already in Position")

            return False

        self.position = {

            "side": "SELL",

            "entry": float(price),

            "quantity": int(quantity),

            "time": datetime.now()
        }

        logger.warning(
            f"PAPER SELL @ {price} | Qty={quantity}"
        )

        return True

    # ----------------------------------------
    # EXIT
    # ----------------------------------------

    def exit(self, price, reason="MANUAL"):

        if self.position is None:

            logger.info("No Position")

            return None

        entry = self.position["entry"]

        quantity = self.position["quantity"]

        side = self.position["side"]

        # BUY P&L
        if side == "BUY":

            pnl = (price - entry) * quantity

        # SELL P&L
        else:

            pnl = (entry - price) * quantity

        pnl = round(pnl, 2)

        self.balance += pnl

        self.total_pnl += pnl

        self.total_trades += 1

        if pnl > 0:

            self.winning_trades += 1

        elif pnl < 0:

            self.losing_trades += 1

        # Save trade
        self._save_trade(
            side=side,
            entry=entry,
            exit_price=price,
            quantity=quantity,
            pnl=pnl,
            reason=reason
        )

        logger.success(
            f"PAPER EXIT | {side} | "
            f"Entry={entry} | Exit={price} | "
            f"Qty={quantity} | P&L=₹{pnl}"
        )

        logger.info(
            f"Paper Balance : ₹{self.balance:.2f}"
        )

        self.position = None

        return pnl

    # ----------------------------------------
    # SAVE TRADE
    # ----------------------------------------

    def _save_trade(
        self,
        side,
        entry,
        exit_price,
        quantity,
        pnl,
        reason
    ):

        with open(
            self.journal_file,
            mode="a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([

                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

                side,

                round(entry, 2),

                round(exit_price, 2),

                quantity,

                pnl,

                reason
            ])

    # ----------------------------------------
    # STATUS
    # ----------------------------------------

    def status(self):

        return {

            "balance": round(self.balance, 2),

            "total_pnl": round(self.total_pnl, 2),

            "total_trades": self.total_trades,

            "winning_trades": self.winning_trades,

            "losing_trades": self.losing_trades
        }

    # ----------------------------------------
    # REPORT
    # ----------------------------------------

    def report(self):

        if self.total_trades > 0:

            win_rate = (
                self.winning_trades /
                self.total_trades
            ) * 100

        else:

            win_rate = 0

        logger.info("========================================")
        logger.info("       PAPER TRADING REPORT")
        logger.info("========================================")

        logger.info(
            f"Starting Balance : ₹{self.starting_balance:.2f}"
        )

        logger.info(
            f"Current Balance  : ₹{self.balance:.2f}"
        )

        logger.info(
            f"Total Trades     : {self.total_trades}"
        )

        logger.info(
            f"Winning Trades   : {self.winning_trades}"
        )

        logger.info(
            f"Losing Trades    : {self.losing_trades}"
        )

        logger.info(
            f"Win Rate         : {win_rate:.2f}%"
        )

        logger.info(
            f"Total P&L        : ₹{self.total_pnl:.2f}"
        )

        logger.info("========================================")