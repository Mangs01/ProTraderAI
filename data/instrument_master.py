import requests
import pandas as pd
from loguru import logger


class InstrumentMaster:

    URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

    def __init__(self):

        self.df = None

    def load(self):

        logger.info("Downloading Instrument Master...")

        data = requests.get(self.URL).json()

        self.df = pd.DataFrame(data)

        logger.success(f"{len(self.df)} Instruments Loaded")

        return self.df