import functools
import re
from typing import TypeAlias

from bs4 import BeautifulSoup, Tag

Selectable: TypeAlias = BeautifulSoup | Tag


def select_one_or_raise(soup: Selectable, selector: str) -> Tag:
    el = soup.select_one(selector)
    if el is None:
        raise ValueError()

    return el


def get_stripped_text(el: Tag):
    text = el.get_text(" ")
    text = text.strip().replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def search_or_raise(patt: str, text: str, **kwargs) -> re.Match:
    m = re.search(patt, text, **kwargs)
    if m is None:
        raise ValueError()

    return m


def has_class(el: Tag, cls: str):
    classes: list[str] = el.get("class", [])  # type: ignore
    return cls in classes


def get_children(el: Tag):
    return el.findChildren(recursive=False)


def get_self_text(el: Tag) -> str:
    text = el.find(recursive=False, string=True)
    assert text is not None, text
    assert isinstance(text, str), str(text)

    return text
