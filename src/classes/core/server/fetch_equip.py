import re

import loguru
import requests
from bs4 import BeautifulSoup, Tag

from config import paths
from utils.html import get_stripped_text, select_one_or_raise
from utils.misc import load_toml

LOGGER = loguru.logger.bind(tags=["equip_parser"])


def parse_equip_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    name, alt_name = _parse_name(soup)

    return dict(
        name=name,
        alt_name=alt_name,
    )


def _parse_name(doc: BeautifulSoup) -> tuple[str, str | None]:
    fst_el = select_one_or_raise(doc, "#showequip > div")
    snd_el = select_one_or_raise(doc, "#showequip > div:nth-child(2)")

    if snd_el.attrs.get("id") == "equip_extended":
        name = _parse_name_el(fst_el)
        alt_name = None
    else:
        name = _parse_name_el(snd_el)
        alt_name = _parse_name_el(fst_el)

    return name, alt_name


def _parse_name_el(el: Tag):
    name = get_stripped_text(el)

    # Handle no custom font, causing letters to be crops of a sprite sheet
    # with crop coordinates determined by class
    if not name:
        line_els = el.select(".fc")

        name = ""
        for line_el in line_els:
            letter_els = line_el.select(".fc > div")

            for el in letter_els:
                cls = el["class"][0]
                print(cls)
                if cls in _FONT_CLASS_MAP:
                    name += _FONT_CLASS_MAP[cls]
                else:
                    LOGGER.error(f"Unknown character in default HV font: {cls}")

            if line_el is not line_els[-1]:
                name += " "

    return name


def fetch_equip_html(eid: int, key: str, is_isekai: bool):
    session = _init_hv_session()

    if not is_isekai:
        url = f"https://hentaiverse.org/equip/{eid}/{key}"
    else:
        url = f"https://hentaiverse.org/isekai/equip/{eid}/{key}"

    LOGGER.info(f"Fetching {url}")
    resp = session.get(url)
    resp.raise_for_status()

    return resp.text


def _init_hv_session():
    secrets = load_toml(paths.SECRETS_FILE).value

    session = requests.Session()
    for k, v in secrets["HV_COOKIES"].items():
        session.cookies.set(k, str(v))

    return session


_FONT_CLASS_MAP = dict(
    c59=" ",
    c39=" ",
    c5a="a",
    c5b="b",
    c5c="c",
    c5d="d",
    c5e="e",
    c5f="f",
    c5g="g",
    c5h="h",
    c5i="i",
    c5j="j",
    c5k="k",
    c5l="l",
    c5m="m",
    c5n="n",
    c5o="o",
    c5p="p",
    c5q="q",
    c5r="r",
    c5s="s",
    c5t="t",
    c5u="u",
    c5v="v",
    c5w="w",
    c5x="x",
    c5y="y",
    c5z="z",
    c40="0",
    c41="1",
    c42="2",
    c43="3",
    c44="4",
    c45="5",
    c46="6",
    c47="7",
    c48="8",
    c49="9",
    c3a="a",
    c3b="b",
    c3c="c",
    c3d="d",
    c3e="e",
    c3f="f",
    c3g="g",
    c3h="h",
    c3i="i",
    c3j="j",
    c3k="k",
    c3l="l",
    c3m="m",
    c3n="n",
    c3o="o",
    c3p="p",
    c3q="q",
    c3r="r",
    c3s="s",
    c3t="t",
    c3u="u",
    c3v="v",
    c3w="w",
    c3x="x",
    c3y="y",
    c3z="z",
)
