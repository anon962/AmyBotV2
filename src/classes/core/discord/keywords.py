from abc import ABC, abstractclassmethod
import re
from datetime import datetime, timezone

from utils.parse import int_to_price, price_to_int


class Keyword(ABC):
    prefix: str

    @abstractclassmethod
    def extract(cls, text: str) -> tuple[str, str | None]:
        """Extract value for later parsing

        Args:
            text:

        Returns:
            Tuple of
                - string with value removed
                - value
        """
        ...


def _extract(text: str, patt: re.Pattern):
    m = re.search(patt, text)
    if m:
        rem = text[: m.start(1)] + text[m.end(1) :]
        val = m.group(2)
        return (rem, val)
    else:
        return (text, None)


class YearKey(Keyword):
    prefix = "year"

    @classmethod
    def extract(cls, text: str) -> tuple[str, str | None]:
        """Extract years like "2022" """
        PATT = re.compile(r"\b((\d{4}))\b")
        return _extract(text, PATT)

    @classmethod
    def convert(cls, text: str) -> float | None:
        subbed = re.sub(r"[^\d]", "", text)
        if not subbed:
            return None

        year = int(subbed)
        ts = datetime(year, 1, 1, tzinfo=timezone.utc).timestamp()
        return ts


class MinPriceKey(Keyword):
    prefix = "min"

    @classmethod
    def extract(cls, text: str) -> tuple[str, str | None]:
        """Extract prices like "min500k" """
        PATT = re.compile(r"\b(min ?(\d+[mkc]?))")
        return _extract(text, PATT)

    @classmethod
    def convert(cls, text: str) -> int | None:
        try:
            return price_to_int(text)
        except:
            return None


class MaxPriceKey(Keyword):
    prefix = "max"

    @classmethod
    def extract(cls, text: str) -> tuple[str, str | None]:
        """Extract prices like "max500k" """
        PATT = re.compile(r"\b(max ?(\d+[mkc]?))")
        return _extract(text, PATT)

    @classmethod
    def convert(cls, text: str) -> int | None:
        try:
            return price_to_int(text)
        except:
            return None


class LinkKey(Keyword):
    prefix = "link"

    @classmethod
    def extract(cls, text: str) -> tuple[str, str | None]:
        """Check if "link" is in text"""

        PATT = re.compile(r"\b(link)\b")
        m = re.search(PATT, text)
        if m:
            rem = text[: m.start(1)] + text[m.end(1) :]
            return (rem, "")
        else:
            return (text, None)


class ThreadKey(Keyword):
    prefix = "thread"

    @classmethod
    def extract(cls, text: str) -> tuple[str, str | None]:
        """Check if "thread" is in text"""

        PATT = re.compile(r"\b(thread)\b")
        m = re.search(PATT, text)
        if m:
            rem = text[: m.start(1)] + text[m.end(1) :]
            return (rem, "")
        else:
            return (text, None)


class BuyerKey(Keyword):
    prefix = "buyer"

    @classmethod
    def extract(cls, text: str) -> tuple[str, str | None]:
        """Extract users like buyerGENIE"""
        PATT = re.compile(r"\b(buyer(\w*))")
        return _extract(text, PATT)


class SellerKey(Keyword):
    prefix = "seller"

    @classmethod
    def extract(cls, text: str) -> tuple[str, str | None]:
        """Extract users like sellerGENIE"""
        PATT = re.compile(r"\b(seller(\w*))")
        return _extract(text, PATT)
