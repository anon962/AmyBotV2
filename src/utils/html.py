import re
from typing import TypeAlias

from bs4 import BeautifulSoup, Tag

Selectable: TypeAlias = BeautifulSoup | Tag


def select_one_or_raise(soup: Selectable, selector: str):
    el = soup.select_one(selector)
    if el is None:
        raise ValueError()

    return el


def get_stripped_text(el: Tag):
    text = el.get_text(" ")
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text
