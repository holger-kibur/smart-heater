"""
Contains main logic for the fetch script.

Functions:
    fetch_info
    parse_hourly_prices
    parse_day_average
"""

from datetime import datetime, timedelta
from typing import Optional
import json
import requests

from . import log, schedule as cron, util

logger = log.LoggerLazyStatic("FETCH")


class PriceData:
    @classmethod
    def from_nordpool(cls, tree, region_code):
        inst = cls()
        for row in tree:
            for column in row["Columns"]:
                if column["Name"].lower() != region_code.lower():
                    continue
                if not row["IsExtraRow"]:
                    start_time = datetime.fromisoformat(row["StartTime"])
                    price = float(column["Value"].replace(",", ".").replace(" ", ""))
                    inst.add_price_item(start_time, price)
        inst.finalize()
        return inst

    @classmethod
    def from_test_data(cls, tree):
        if "data" not in tree.keys():
            util.exit_critical_bare("Price data file doesn't have the 'data' key!")
        if "weekday" not in tree.keys():
            util.exit_critical_bare("Price data file doesn't have the 'weekday' key!")
        inst = cls()
        start_time = util.next_market_day_start()
        for test_price in tree["data"]:
            inst.add_price_item(start_time, test_price)
            start_time += timedelta(hours=1)
        inst.finalize()
        inst.weekday = tree["weekday"]  # Override from test data
        return inst

    def __init__(self):
        self.data: list[tuple[datetime, float]] = []
        self.weekday: Optional[int] = None

    def add_price_item(self, start_time: datetime, price: float):
        self.data.append((start_time, price))

    def finalize(self):
        self.data = sorted(self.data, key=lambda x: x[1])
        self.weekday = self.data[0][0].weekday()

    def pop_cheapest(self):
        return self.data.pop(0)


def fetch_info(req_url) -> dict:
    """
    Fetch market info from url.
    """
    price_req = requests.get(req_url)
    if price_req.status_code != 200:
        util.exit_critical(
            logger, f"Unable to fetch price table! HTTP code: {price_req.status_code}."
        )
    logger.info("Successfully fetched price table!")

    try:
        price_table = json.loads(price_req.content)
    except json.JSONDecodeError as json_error:
        util.exit_critical(
            logger, f"Couldn't decode price table! Json error: {json_error}"
        )

    try:
        rows = price_table["data"]["Rows"]
    except KeyError:
        util.exit_critical(logger, "Data isn't in the correct format!")

    return rows


def do_fetch(prog_config, test_pricedata=None):
    """
    Do the fetch program logic using the give program configuration.
    """
    if not test_pricedata:
        # Fetch price information from URL
        if prog_config["fetch"]["url"] is None:
            util.exit_critical(logger, "No fetch URL provided in configuration!")
        table_rows = fetch_info(prog_config["fetch"]["url"])
        pricedata = PriceData.from_nordpool(
            table_rows, prog_config["fetch"]["region_code"]
        )
    else:
        pricedata = PriceData.from_test_data(test_pricedata)

    # Build schedule from prices
    # sched_builder = cron.ScheduleBuilder.retrieve_sched(prog_config)
    sched_builder = cron.ScheduleBuilder.retrieve_sched(prog_config)
    rem_minutes = prog_config.get_heating_minutes(pricedata.weekday)
    while rem_minutes > 0:
        start_time, _ = pricedata.pop_cheapest()
        sched_builder.add_heating_slice(start_time, min(rem_minutes, 60))
        rem_minutes -= 60

    # Upload schedule to crontab
    sched_builder.upload(prog_config)
