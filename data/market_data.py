import os
import requests
import pandas as pd

from loguru import logger


class InstrumentMaster:

    URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

    def __init__(self):

        self.file_path = os.path.join(
            "data",
            "OpenAPIScripMaster.json"
        )

        self.df = None

    def download(self):

        logger.info("Downloading Instrument Master...")

        response = requests.get(self.URL, timeout=60)

        response.raise_for_status()

        with open(self.file_path, "wb") as file:
            file.write(response.content)

        logger.success("Instrument Master Downloaded")

    def load(self):

        if not os.path.exists(self.file_path):

            self.download()

        logger.info("Loading Instrument Master...")

        self.df = pd.read_json(self.file_path)

        logger.success(f"Records Loaded : {len(self.df)}")

        return self.df

    def refresh(self):

        self.download()

        return self.load()

    def search(self, symbol):

        if self.df is None:

            self.load()

        result = self.df[
            self.df["symbol"].astype(str).str.upper() == symbol.upper()
        ]

        return result

    def get_token(self, symbol):

        result = self.search(symbol)

        if result.empty:

            return None

        return result.iloc[0]["token"]