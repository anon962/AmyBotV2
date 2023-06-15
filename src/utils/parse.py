from datetime import datetime
from decimal import Decimal
import re
from typing import Any, Generator
from bs4 import NavigableString, Tag

from yarl import URL


def int_to_price(
    price: int | Any, infer_int=False, precision: int | tuple[int, int, int] = 1
) -> str:
    """Converts a number (50,000) to a value with units (50k)

    Args:
        price:
        infer_int: Return ints where possible (eg return 3m instead of 3.0m)
        precision: Number of decimal places. To use different precisions for different magnitudes (c, m, k), provide a sequence. Defaults to 1.
    """
    digits = re.sub(r"[^\d]", "", str(price))
    value = int(digits)
    UNITS = "ckm"

    if value >= 10**6:
        unit_value = value / 10**6
        unit = UNITS[2]
    elif value >= 10**3:
        unit_value = value / 10**3
        unit = UNITS[1]
    else:
        unit_value = value / 1.0
        unit = UNITS[0]

    if infer_int and unit_value.is_integer():
        unit_value = int(unit_value)
    elif isinstance(precision, int):
        unit_value = int(unit_value * 10**precision) / 10**precision
    elif (
        isinstance(precision, tuple)
        and len(precision) == 3
        and all(isinstance(x, int) for x in precision)
    ):
        p = precision[UNITS.index(unit)]
        if p != 0:
            unit_value = int(unit_value * 10**p) / 10**p
        else:
            unit_value = int(unit_value)
    else:
        raise Exception(precision)

    return f"{unit_value}{unit}"


def price_to_int(x: str) -> int:
    # Strip commas and spaces
    text = str(x).replace(",", "").strip().lower()

    # Check format (digits followed by optional suffix)
    m = re.search(r"^\d+.?\d*[mkc]?$", text)
    if m is None:
        raise Exception

    # Parse suffix
    mult = 1
    if text[-1] == "c":
        text = text[:-1]
    elif text[-1] == "k":
        mult = 10**3
        text = text[:-1]
    elif text[-1] == "m":
        mult = 10**6
        text = text[:-1]

    # Parse value
    val = Decimal(text) * mult
    assert val.as_integer_ratio()[1] == 1

    return int(val)


def parse_equip_link(text: str) -> tuple[int, str, bool] | None:
    # http://hentaiverse.org/equip/123487856/579b582136
    patt = r".*hentaiverse\.org/(isekai/)?equip/(\d+)/([A-Za-z\d]{10})"
    if m := re.search(patt, text, flags=re.IGNORECASE):
        [is_isekai, eid, key] = m.groups()
        return (int(eid), key, bool(is_isekai))

    # legacy format -- http://hentaiverse.org/pages/showequip.php?eid=123487856&key=579b582136
    eid = re.search(r"eid=(\d+)", text)
    key = re.search(r"key=([A-Za-z\d]{10})", text)
    is_isekai = "/isekai/" in text
    if eid and key:
        return (int(eid.group(1)), key.group(1), is_isekai)

    return None


def create_equip_link(eid: int, key: str, is_isekai=False) -> URL:
    url = URL("https://hentaiverse.org/")
    if is_isekai:
        url /= "isekai"
    url /= "equip"
    url /= str(eid)
    url /= key
    return url


def parse_post_date(text: str) -> float:
    """Convert date-times found on forum to a utc timestamp

    Formats supported:
        Today, 07:44
        Yesterday, 08:18
        Sep 10 2020, 09:06
    """

    text = text.strip()

    try:
        MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]  # fmt: skip
        months_patt = f"(?:{'|'.join(MONTHS)})"

        very_old_patt = f"({months_patt})" + r" (\d{1,2}) (20\d{2}), (\d{2}):(\d{2})"
        match = re.fullmatch(very_old_patt, text)
        assert match is not None
        vals = match.groups()
        assert len(vals) == 5

        [month, day, year, hour, minute] = vals
        month = MONTHS.index(month) + 1

        ts = datetime(int(year), month, int(day), int(hour), int(minute)).timestamp()
        return ts
    except AssertionError:
        pass

    try:
        match = re.fullmatch(r"Yesterday, (\d{2}):(\d{2})", text)
        assert match is not None

        vals = match.groups()
        assert len(vals) == 2

        [hour, minute] = vals
        today = datetime.now()
        day = today.day - 1

        ts = datetime(today.year, today.month, day, int(hour), int(minute)).timestamp()
        return ts
    except AssertionError:
        pass

    try:
        match = re.fullmatch(r"Yesterday, (\d{2}):(\d{2})", text)
        assert match is not None

        vals = match.groups()
        assert len(vals) == 2

        [hour, minute] = vals
        today = datetime.now()

        ts = datetime(
            today.year, today.month, today.day, int(hour), int(minute)
        ).timestamp()
        return ts
    except AssertionError:
        pass

    raise Exception(f"Invalid date: {text}")
