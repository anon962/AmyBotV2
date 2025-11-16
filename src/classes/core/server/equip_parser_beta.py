import re
from typing import cast

import loguru
from bs4 import BeautifulSoup, Tag
from soupsieve import select_one

from classes.core.server.parse_equip_name import parse_equip_name
from utils.html import (
    get_children,
    get_self_text,
    get_stripped_text,
    search_or_raise,
    select_one_or_raise,
)

LOGGER = loguru.logger.bind(tags=["equip_parser"])


def parse_equip_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    name, alt_name = _parse_name(soup)
    try:
        name_parts = parse_equip_name(name)
    except Exception:
        LOGGER.exception(name)
        name_parts = None
    category, level, is_tradeable = _parse_equip_category(soup)
    status = _parse_status(soup)
    weapon_damage = _parse_weapon_damage(soup)
    misc_stats = _parse_misc_stats(soup)
    cat_stats = _parse_category_stats(soup)
    upgrades = _parse_upgrades(soup)
    enchants = _parse_enchants(soup)
    owner = _parse_owner(soup)

    result = dict(
        is_beta=True,
        name=name,
        name_parts=name_parts,
        alt_name=alt_name,
        category=category,
        level=level,
        is_tradeable=is_tradeable,
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

    return result


def _parse_name(doc: BeautifulSoup) -> tuple[str, str | None]:
    fst_el = select_one_or_raise(doc, ".showequip > div")
    name, alt_name = _parse_name_el(fst_el)
    return name, alt_name


def _parse_name_el(el: Tag):
    children = get_children(el)
    assert len(children) in [0, 2]

    if len(children) == 0:
        name = get_stripped_text(el)
        alt_name = None
    else:
        name = get_stripped_text(children[1]).strip("()")
        alt_name = get_stripped_text(children[0])

    return name, alt_name


def _parse_equip_category(soup: BeautifulSoup) -> tuple[str, int | str, bool]:
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

    tradability_el = select_one_or_raise(category_el, "span")
    is_tradable = get_stripped_text(tradability_el) == "Tradeable"

    return category, level, is_tradable


def _parse_status(soup: BeautifulSoup) -> dict:
    status_el = select_one_or_raise(soup, ".eq > div:nth-child(2)")
    text = status_el.get_text().strip()

    if text == "Salvaged - Repair Required":
        condition = None
        energy = None
    else:
        # Condition: 68%     Energy: 35%
        m = search_or_raise(
            r"Condition: (\d+(?:\.\d+)?)% \s+ Energy: (?:(\d+(?:\.\d+)?)%|(N\/A))",
            text,
        )

        condition = float(m.group(1))

        if m.group(2):
            energy = float(m.group(2))
        else:
            energy = None

    return dict(
        condition=dict(
            current=condition,
            max=100,
        ),
        potency=dict(
            tier=0,
            current_xp=0,
            max_xp=1,
        ),
    )


def _parse_weapon_damage(soup: BeautifulSoup) -> dict | None:
    line_els = soup.select(".eq > div:not(.ex):not(.ep)")[2:]
    if not len(line_els):
        return None

    d: dict = {
        "Attack Damage": None,
        "strikes": [],
        "status_effects": [],
    }

    for el in line_els:
        # +895 Crushing Damage
        m_damage = re.search(r"^\+ (\d+) (.*) Damage$", get_stripped_text(el))
        if m_damage:
            damage_value = int(m_damage.group(1))
            damage_type = m_damage.group(2)

            raw_base = cast(str, el["title"])
            m_base = search_or_raise(r"Base: (\d+(?:\.\d+)?)", raw_base)
            damage_base = float(m_base.group(1))

            d["Attack Damage"] = dict(
                type=damage_type,
                value=damage_value,
                base=damage_base,
            )
            continue

        # Dark Strike + Void Strike
        m_strike = re.search(r"(.*?) Strike(?: \+ (.*) Strike)?", get_stripped_text(el))
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

        if "title" in el.attrs:
            m_base = search_or_raise(
                r"Base: (\d+(?:\.\d+)?)",
                cast(str, el.attrs["title"]),
            )
            base_value = float(m_base.group(1))
        else:
            base_value = 0

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
    assert len(children) == 2, children

    if "title" in el.attrs:
        m_base = search_or_raise(
            r"Base: (\d+(?:\.\d+)?)",
            cast(str, el.attrs["title"]),
        )
        base_value = float(m_base.group(1))
    else:
        base_value = 0

    name = get_self_text(children[0])
    value = float(get_stripped_text(children[1]).strip("+"))
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
        t = get_stripped_text(el)
        m = re.search(r"(.*) Lv\.(\d+)", t)
        if m:
            name = m.group(1)
            level = int(m.group(2))
            enchants[name] = level
        else:
            enchants[t] = 1

    return enchants


def _parse_owner(soup: BeautifulSoup):
    # Rewarded as a Clear Bonus to ... on 2025-11-04
    # Current Owner: Equipment Shop

    # Dropped by Ujinao Houjou for ... on 2025-11-04
    # Current Owner: Equipment Shop

    footer_el = select_one_or_raise(soup, ".showequip > div:last-child")

    children = get_children(footer_el)
    assert len(children) == 2, children

    source_el = select_one_or_raise(children[0], "a")
    source_name = get_stripped_text(source_el)
    source_uid = int(
        search_or_raise(
            r"showuser=(\d+)",
            source_el["href"],  # type: ignore
        ).group(1)
    )
    source_date = children[0].getText().split()[-1]

    source_mob = None
    source_mob_match = re.search(
        r"^Dropped by (.*) for$",
        children[0].contents[0].get_text().strip(),
    )
    if source_mob_match:
        source_mob = source_mob_match.group(1)

    owner_el = select_one("a", children[1])
    if owner_el:
        owner_name = get_stripped_text(owner_el)
        owner_uid = int(
            search_or_raise(
                r"showuser=(\d+)",
                owner_el["href"],  # type: ignore
            ).group(1)
        )
    else:
        owner_name = "Equipment Shop"
        owner_uid = None

    return dict(
        name=owner_name,
        uid=owner_uid,
        date=source_date,
        source_name=source_name,
        source_uid=source_uid,
        source_mob=source_mob,
    )
