import re
from dataclasses import dataclass
from typing import NamedTuple

import yarl


@dataclass
class EquipLink:
    is_expanded: bool

    eid: int
    key: str
    is_isekai: bool


def on_equip_message(text: str):
    links = _extract_links(text) + _extract_legacy_links(text)


def _extract_links(text: str) -> list[EquipLink]:
    # http://hentaiverse.org/equip/123487856/579b582136
    matches = re.findall(
        r"(!?).*hentaiverse\.org/(isekai/)?equip/(\d+)/([A-Za-z\d]{10})", text
    )

    parsed = [
        EquipLink(
            bool(is_expanded),
            int(eid),
            key,
            bool(is_isekai),
        )
        for is_expanded, is_isekai, eid, key in matches
    ]

    return parsed


def _extract_legacy_links(text: str) -> list[EquipLink]:
    # http://hentaiverse.org/pages/showequip.php?eid=123487856&key=579b582136
    candidates = re.findall(r"(!?)(.*hentaiverse\.org/[^\s]+)", text)

    matches = []
    for prefix, raw_link in candidates:
        url = yarl.URL(raw_link)

        raw_eid = url.query.get("eid")
        if not raw_eid:
            continue

        try:
            eid = int(raw_eid)
        except ValueError:
            continue

        key = url.query.get("key")
        if not key:
            continue

        parts = [p.lower() for p in parts]
        is_isekai = "isekai" in parts

        matches.append(
            EquipLink(
                bool(prefix),
                int(eid),
                key,
                is_isekai,
            )
        )

    return matches
