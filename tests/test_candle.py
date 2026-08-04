from live.candle_builder import CandleBuilder


def test_builder():

    builder = CandleBuilder()

    tick = {
        "token": "3045",
        "ltp": 1038.50,
        "exchange_timestamp": 1783512000000
    }

    candle = builder.update(tick)

    print(candle)


if __name__ == "__main__":
    test_builder()