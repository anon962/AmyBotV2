import json
import re
from typing import cast

import loguru
import requests
from bs4 import BeautifulSoup, Tag

from config import paths
from utils.html import (
    get_children,
    get_self_text,
    get_stripped_text,
    search_or_raise,
    select_one_or_raise,
)
from utils.misc import load_toml

LOGGER = loguru.logger.bind(tags=["equip_parser"])


def _init_hv_session():
    secrets = load_toml(paths.SECRETS_FILE).value

    session = requests.Session()
    for k, v in secrets["HV_COOKIES"].items():
        session.cookies.set(k, str(v))

    return session


def fetch_equip_html(eid: int, key: str, is_isekai: bool):
    session = _init_hv_session()

    if not is_isekai:
        url = f"https://hentaiverse.org/equip/{eid}/{key}"
    else:
        url = f"https://hentaiverse.org/isekai/equip/{eid}/{key}"

    LOGGER.info(f"Fetching {url}")
    resp = session.get(url)

    return resp


def parse_equip_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    name, alt_name = _parse_name(soup)
    category, level = _parse_equip_category(soup)
    status = _parse_status(soup)
    weapon_damage = _parse_weapon_damage(soup)
    misc_stats = _parse_misc_stats(soup)
    cat_stats = _parse_category_stats(soup)
    upgrades = _parse_upgrades(soup)
    enchants = _parse_enchants(soup)
    owner = _parse_owner(soup)

    return dict(
        name=name,
        alt_name=alt_name,
        category=category,
        level=level,
        weapon_damage=weapon_damage,
        stats=dict(
            misc=misc_stats,
            **cat_stats,
        ),
        upgrades=upgrades,
        enchants=enchants,
        owner=owner,
        **status,
    )


def infer_equip_stats(equip: dict, ranges_override: dict | None = None):
    percentiles = _calc_percentiles(equip, ranges_override)

    return dict(
        percentiles=percentiles,
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

    # When no custom font, letters are images
    # Literally crops of a sprite sheet with coordinates determined by class
    if not name:
        line_els = el.select(".fc")

        name = ""
        for line_el in line_els:
            letter_els = line_el.select(".fc > div")

            for el in letter_els:
                cls = el["class"][0]
                if cls in _FONT_CLASS_MAP:
                    name += _FONT_CLASS_MAP[cls]
                else:
                    LOGGER.error(f"Unknown character in default HV font: {cls}")

            if line_el is not line_els[-1]:
                name += " "

    return name


def _parse_equip_category(soup: BeautifulSoup) -> tuple[str, int | str]:
    category_el = select_one_or_raise(soup, ".eq > div")

    text = get_self_text(category_el)

    parts = text.replace("\xa0", " ").split("Level")
    if len(parts) == 2:
        category = parts[0].strip()

        raw_level = parts[1].strip()
        if raw_level == "Unassigned":
            level = "Unassigned"
        else:
            level = int(raw_level)
    elif len(parts) == 1:
        category = parts[0].strip()
        level = "Soulbound"
    else:
        raise ValueError(text)

    return category, level


def _parse_status(soup: BeautifulSoup) -> dict:
    status_el = select_one_or_raise(soup, ".eq > div:nth-child(2)")

    # Condition: 519 / 523 (100%)     Potency Tier: 8 (184 / 3777)
    m = search_or_raise(
        r"Condition: (\d+) / (\d+) \(\d+%\) \s+ Potency Tier: (\d+) \((.*)\)",
        status_el.get_text().replace("\xa0", " "),
    )

    current_condition = int(m.group(1))
    max_condition = int(m.group(2))
    potency_tier = int(m.group(3))

    current_potency_xp = None
    max_potency_xp = None
    if m.group(4) != "MAX":
        parts = m.group(4).split("/")
        current_potency_xp = int(parts[0])
        max_potency_xp = int(parts[1])

    return dict(
        condition=dict(
            current=current_condition,
            max=max_condition,
        ),
        potency=dict(
            tier=potency_tier,
            current_xp=current_potency_xp,
            max_xp=max_potency_xp,
        ),
    )


def _parse_weapon_damage(soup: BeautifulSoup) -> dict | None:
    line_els = soup.select(".eq > div:not(.ex):not(.ep)")[2:]
    if not len(line_els):
        return None

    d: dict = dict(
        damage=None,
        strikes=[],
        status_effects=[],
    )

    for el in line_els:
        # +895 Crushing Damage
        m_damage = re.search(r"^\+ (\d+) (.*) Damage$", get_stripped_text(el))
        if m_damage:
            damage_value = int(m_damage.group(1))
            damage_type = m_damage.group(2)

            raw_base = cast(str, el["title"])
            m_base = search_or_raise(r"Base: (\d+(?:\.\d+)?)", raw_base)
            damage_base = float(m_base.group(1))

            d["damage"] = dict(type=damage_type, value=damage_value, base=damage_base)
            continue

        # Dark Strike + Void Strike
        m_strike = re.search(r"(.*) Strike(?: \+ (.*) Strike)?", get_stripped_text(el))
        if m_strike:
            d["strikes"].append(m_strike.group(1).strip())

            if m_strike.group(2):
                d["strikes"].append(m_strike.group(2).strip())

            continue

        # Other, eg "Ether Tap: 40% chance - 4 turns"
        d["status_effects"].append(get_stripped_text(el))

    return d


def _parse_misc_stats(soup: BeautifulSoup):
    els = soup.select(".eq > .ex > div")

    stats = dict()
    for el in els:
        # 0 = empty
        # 2 = $name: $value
        # 3 = $name: $value %
        children = el.select("div")
        assert len(children) in [0, 2, 3]
        if not children:
            continue

        m_base = search_or_raise(
            r"Base: (\d+(?:\.\d+)?)",
            cast(str, el["title"]),
        )
        base_value = float(m_base.group(1))

        name = get_stripped_text(children[0])
        value = float(get_stripped_text(children[1]).strip("+"))

        stats[name] = dict(
            value=value,
            base=base_value,
        )

    return stats


def _parse_category_stats(soup: BeautifulSoup):
    cat_els = soup.select(".eq > .ep")

    stats = dict()
    for cat_el in cat_els:
        children = get_children(cat_el)
        assert len(children) >= 2

        header_el = children[0]
        assert len(get_children(header_el)) == 0
        cat_name = get_stripped_text(header_el)

        cat_stats = dict()
        for el in children[1:]:
            st = _parse_single_cat_stat(el)
            cat_stats[st["name"]] = dict(
                value=st["value"],
                base=st["base"],
            )

        stats[cat_name] = cat_stats

    return stats


def _parse_single_cat_stat(el: Tag):
    children = get_children(el)
    assert len(children) == 1, children

    m_base = search_or_raise(
        r"Base: (\d+(?:\.\d+)?)",
        cast(str, el["title"]),
    )
    base_value = float(m_base.group(1))

    name = get_self_text(el).strip(" +-")
    value = float(get_stripped_text(children[0]).strip("+"))
    return dict(
        name=name,
        value=value,
        base=base_value,
    )


def _parse_upgrades(soup: BeautifulSoup):
    els = soup.select("#eu > span")

    upgrades = dict()
    for el in els:
        m = search_or_raise(r"(.*) Lv\.(\d+)", get_stripped_text(el))
        name = m.group(1)
        level = int(m.group(2))
        upgrades[name] = level

    return upgrades


def _parse_enchants(soup: BeautifulSoup):
    els = soup.select("#ep > span")

    enchants = dict()
    for el in els:
        m = search_or_raise(r"(.*) Lv\.(\d+)", get_stripped_text(el))
        name = m.group(1)
        level = int(m.group(2))
        enchants[name] = level

    return enchants


def _parse_owner(soup: BeautifulSoup):
    owner_el = select_one_or_raise(soup, "#showequip > div:last-child")
    assert get_self_text(owner_el).strip() == "Current Owner:"

    href_el = select_one_or_raise(owner_el, "a")
    href: str = href_el["href"]  # type: ignore

    name = get_stripped_text(href_el)
    m_uid = search_or_raise(r"showuser=(\d+)", href)
    uid = int(m_uid.group(1))

    return dict(name=name, uid=uid)


# based off LPR script and wiki page: https://ehwiki.org/wiki/The_Forge#Upgrade
def _calc_percentiles(equip: dict, ranges_override: dict | None = None):
    if ranges_override is None:
        ranges = json.loads(paths.RANGES_FILE.read_text())
    else:
        ranges = ranges_override

    path_options = _enumerate_range_path_options_from_name(equip["name"])

    percentiles = dict()

    if equip["weapon_damage"]:
        percentiles["weapon_damage"] = {
            "Attack Damage": _calc_percentile(
                ranges,
                path_options,
                "Attack Damage",
                equip["weapon_damage"]["damage"]["base"],
            ),
        }

    for cat, stats in equip["stats"].items():
        percentiles[cat] = dict()

        for st, d in stats.items():
            if cat == "Damage Mitigations":
                st += " MIT"
            elif cat == "Spell Damage":
                st += " EDB"
            elif cat == "Proficiency":
                st += " PROF"

            percentiles[cat][st] = _calc_percentile(
                ranges,
                path_options,
                st,
                d["base"],
            )

    return percentiles


def _enumerate_range_path_options_from_name(name: str) -> list[dict]:
    """
    Equip names are structured as follows:
        quality (prefix) (category) slot (suffix)

    In the percentile range data...
    For weapons, the path to the min / max values looks like
        slot -> quality -> stat -> prefix + suffix
    Armor is similar, with an additional category key
        category -> slot -> quality -> stat -> prefix + suffix

    Since most of the name is optional, which word corresponds to which key can be ambiguous
    For example...
        Average Axe (of) Slaughter = quality + slot + suffix
        Average Cotton Pants = quality + category + slot

    To avoid a giant whitelist of valid words for each key, we'll just try out all combinations.

    {
        "Axe": {
            "Legendary": {
                "lastUpdate": 1580056121,
                "Attack Damage": {
                    "all | Slaughter": {
                        "min": 67.72,
                        "max": 75.92
                    },
                    "all | not!Slaughter": {
                        "min": 53.39,
                        "max": 59.87
                    }
                },
                "Attack Accuracy": {
                    "all | all": {
                        "min": 11.04,
                        "max": 12.81
                    }
                },
            }
        },
        "Cotton": {
            "Shoes": {
                "Legendary": {
                    "lastUpdate": 1580896046,
                    "Attack Accuracy": {
                        "all | all": {
                            "min": 3.22,
                            "max": 3.83
                        }
                    },
                    "Magic Accuracy": {
                        "all | all": {
                            "min": 2.99,
                            "max": 3.49
                        }
                    },
                    ...
                }
            }
        }
        ...
    }
    """

    # Split name into [quality, (prefix), (category), slot, (suffix)]
    # eg Peerless Chaged Phase Cap of Surtr --> [Peerless, Charged, Phase, Cap, Surtr]
    parts = name.split(" ")
    parts = [p for p in parts if p not in ["of", "Of", "the", "The", "Shield", "Staff"]]
    assert len(parts) >= 2 and len(parts) <= 5, parts

    # Suffix can exist by itself but prefix always requires a suffix
    path_options = []
    if len(parts) == 5:
        quality, prefix, category, slot, suffix = parts
        path_options.append(
            dict(
                quality=quality,
                prefix=prefix,
                category=category,
                slot=slot,
                suffix=suffix,
            )
        )
    elif len(parts) == 4:
        quality, a, b, c = parts
        path_options.append(
            dict(quality=quality, prefix=a, category=None, slot=b, suffix=c)
        )
        path_options.append(
            dict(quality=quality, prefix=None, category=a, slot=b, suffix=c)
        )
    elif len(parts) == 3:
        quality, a, b = parts
        path_options.append(
            dict(quality=quality, prefix=None, category=a, slot=b, suffix=None)
        )
        path_options.append(
            dict(quality=quality, prefix=None, category=None, slot=a, suffix=b)
        )
    elif len(parts) == 2:
        quality, a = parts
        path_options.append(
            dict(quality=quality, prefix=None, category=None, slot=a, suffix=None)
        )

    return path_options


def _find_min_max(ranges: dict, path: dict, stat: str) -> tuple[float, float] | None:
    def walk(d: dict, keys: list[str]):
        v = d
        for k in keys:
            if k in v:
                v = v[k]
            else:
                return None

        return v

    def is_match(req: str, value: str | None) -> bool:
        """
        eg
            value   = "Slaughter"
            req     = "Slaughter"
            returns True

            value   = "Slaughter"
            req     = "not!Slaughter"
            returns False

            value   = "Banshee"
            req     = "Slaughter"
            returns False

            value   = "Banshee"
            req     = "not!Slaughter"
            returns True
        """

        if req == "all":
            return True

        is_negative = req.startswith("not!")
        patt = req.strip("not!")

        result = patt == value
        if is_negative:
            result = not result

        return result

    # Try slot -> quality -> stat
    d = walk(ranges, [path["slot"], path["quality"], stat])

    # Try category -> slot -> quality -> stat
    if not d and path["category"]:
        d = walk(ranges, [path["category"], path["slot"], path["quality"], stat])

    if not d:
        return None

    for req, min_max in d.items():
        prefix_req, suffix_req = req.split(" | ")

        if not is_match(prefix_req, path["prefix"]):
            continue
        if not is_match(suffix_req, path["suffix"]):
            continue

        return (min_max["min"], min_max["max"])

    return None


def _calc_percentile(
    ranges: dict,
    path_options: list[dict],
    stat: str,
    base_value: float,
) -> float | None:
    for p in path_options:
        r = _find_min_max(ranges, p, stat)
        if not r:
            continue

        mn, mx = r
        if mn == mx:
            if base_value != mn:
                LOGGER.warning(
                    f"Stat with zero-width range received value outside range: {stat} [{mn}, {mx}] {base_value} {p}"
                )

            return 1.0

        percentile = (base_value - mn) / (mx - mn)
        if percentile < -0.1 or percentile > 1.1:
            LOGGER.warning(
                f"Incorrect range for {stat}: {percentile} [{mn}, {mx}] {base_value} {p}"
            )

        print(p, stat, base_value, mn, mx)
        return percentile

    return None


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
