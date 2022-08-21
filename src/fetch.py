"""
Contains main logic for the fetch script.

Functions:
    fetch_info
    parse_hourly_prices
    parse_day_average
"""

from datetime import datetime
import json
import requests

from . import log, schedule as cron, util

logger = log.LoggerFactory.get_logger("FETCH")


def fetch_info(req_url) -> dict:
    """
    Fetch market info from url.
    """
    price_req = requests.get(req_url)
    if price_req.status_code != 200:
        util.exit_critical(
            logger, f"Unable to fetch price table! HTTP code: {price_req.status_code}.")
    logger.info("Successfully fetched price table!")

    try:
        price_table = json.loads(price_req.content)
    except json.JSONDecodeError as json_error:
        util.exit_critical(
            logger, f"Couldn't decode price table! Json error: {json_error}")

    try:
        rows = price_table["data"]["Rows"]
    except KeyError:
        util.exit_critical(logger, "Data isn't in the correct format!")

    return rows


def parse_hourly_prices(country, info_rows) -> list:
    """
    Parse the hourly prices for the given country from info_rows.

    This method returns a list of price-hour dicts sorted in ascending order by price.
    """

    price_info = []

    for row in info_rows:
        for column in row["Columns"]:
            if column["Name"] == country:
                if not row["IsExtraRow"]:
                    print(column['Value'], row['StartTime'])
                    price_info.append({
                        "start_time": datetime.fromisoformat(row["StartTime"]),
                        "price": float(column["Value"].replace(",", ".").replace(' ', '')),
                    })

    # Fail the script if the prices are not for tomorrow
    if price_info[0]['start_time'] < util.next_market_day_start():
        util.exit_critical(
            logger,
            "Fetched today's price information, not tomorrows as expected!")

    return sorted(price_info, key=lambda x: x["price"])


def do_fetch(prog_config):
    """
    Do the fetch program logic using the give program configuration.
    """

    # Fetch price information from URL
    if prog_config["fetch"]["url"] is None:
        util.exit_critical(logger, "No fetch URL provided in configuration!")
    table_rows = fetch_info(prog_config["fetch"]["url"])

    # Parse hourly prices
    pricelist = parse_hourly_prices(
        prog_config["fetch"]["region_code"], table_rows)

    # Build schedule from prices
    sched_builder = cron.ScheduleBuilder()
    rem_minutes = prog_config.get_heating_minutes(pricelist[0]["start_time"])
    for price_entry in pricelist:
        if rem_minutes <= 0:
            break
        sched_builder.add_heating_slice(
            price_entry["start_time"], min(rem_minutes, 60))
        rem_minutes -= 60

    # Upload schedule to crontab
    sched_builder.upload(prog_config)
