from datetime import datetime


class TickParser:

    @staticmethod
    def parse(message):

        return {

            "token": message.get("token"),

            "exchange": message.get("exchange_type"),

            "ltp": message.get("last_traded_price", 0) / 100,

            "time": datetime.now().strftime("%H:%M:%S")

        }