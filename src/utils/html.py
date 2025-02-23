import functools
import re
from typing import TypeAlias, TypeVar

from bs4 import BeautifulSoup, NavigableString, PageElement, Tag

Selectable: TypeAlias = BeautifulSoup | Tag

T = TypeVar("T")


def select_one_or_raise(soup: Selectable, selector: str) -> Tag:
    el = soup.select_one(selector)
    if el is None:
        raise ValueError()

    return el


def get_stripped_text(el: PageElement):
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
    return list(el.findChildren(recursive=False))


def get_self_text(el: Tag) -> str:
    text = el.find(recursive=False, string=True)
    assert text is not None, text
    assert isinstance(text, str), str(text)

    return text


def get_attr_or_raise(el: Tag, attr: str) -> str:
    if attr not in el.attrs:
        raise ValueError()

    return el.attrs[attr]


def get_tag(el: Tag) -> str:
    return el.name.lower()


def first(xs: list[T]) -> T | None:
    if len(xs):
        return xs[0]
    else:
        return None
