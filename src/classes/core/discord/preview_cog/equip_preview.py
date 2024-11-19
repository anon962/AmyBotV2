import re
from dataclasses import dataclass

import discord
import requests
import tomli
import yarl

from config.paths import CONFIG_DIR


@dataclass
class EquipLink:
    is_expanded: bool

    eid: int
    key: str
    is_isekai: bool


def extract_equip_links(text: str):
    return _extract_links(text) + _extract_legacy_links(text)


def generate_equip_preview(links: list[EquipLink]) -> tuple[list[str], bool]:
    config = tomli.loads((CONFIG_DIR / "preview_config.toml").read_text())

    with_info = []
    has_fail = False
    for l in links:
        d = _fetch_equip_info(config["equip"]["api_url"], l.eid, l.key, l.is_isekai)
        with_info.append(dict(link=l, info=d))

        if d is None:
            has_fail = True

    previews = []
    for d in with_info:
        if d["link"].is_expanded:
            previews.append(
                _format_expanded_equip_preview(config, d["info"]),
            )
        else:
            previews.append(
                _format_terse_equip_preview(
                    config,
                    d["info"],
                )
            )

    return previews, has_fail


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


def _fetch_equip_info(api_url: str, eid: int, key: str, is_isekai: bool):
    resp = requests.get(f"{api_url}/equip?eid={eid}&key={key}&is_isekai={is_isekai}")

    if resp.status_code == 200:
        return resp.json()
    else:
        return None


def _format_terse_equip_preview(config: dict, info: dict):
    cfg = config["equip"]["terse"]
    use_legendary_ranges = config["equip"]["use_legendary_ranges"]

    if use_legendary_ranges:
        percentiles = info["calculations"]["legendary_percentiles"]
    else:
        percentiles = info["calculations"]["percentiles"]

    stats_to_show: list[list[str]] = []
    for eq, stat_paths in cfg["required_stats"].items():
        words = eq.split(" ")
        is_match = all(w in info["name"].lower() for w in words)
        if is_match:
            stats_to_show.extend(stat_paths)

    for cat, stats in percentiles.items():
        for name, p in stats.items():
            if p is None:
                continue

            path = [cat, name]
            if path in stats_to_show:
                continue

            is_negative = path in cfg["negative_stats"]

            if not is_negative and p >= cfg["min_percentile"]:
                stats_to_show.append(path)
            elif is_negative and p <= (100 - cfg["min_percentile"]):
                stats_to_show.append(path)

    stat_strs = []
    for path in stats_to_show:
        name = _find_abbrv(config, path) or path[-1]
        p = _get_percentile(percentiles, path[0], path[1])

        if p is not None:
            stat_strs.append(f"{name} {p:.0%}")

    msg = _get_header(info)
    msg += "\n" + ", ".join(stat_strs)
    msg = f"```py\n{msg}\n```"

    return msg


def _format_expanded_equip_preview(config: dict, info: dict):
    cfg = config["equip"]["expanded"]
    use_legendary_ranges = config["equip"]["use_legendary_ranges"]

    if use_legendary_ranges:
        percentiles = info["calculations"]["legendary_percentiles"]
    else:
        percentiles = info["calculations"]["percentiles"]

    # Bin stats-to-show
    cols = []
    seen = set()
    for col_cfg in cfg["categories"]:
        c = dict(header=col_cfg["name"], vals=[], cells=[])
        for path in col_cfg["stat_paths"]:
            p = _get_percentile(percentiles, path[0], path[1])
            if not p:
                continue

            name = _find_abbrv(config, path) or path[-1]
            c["vals"].append(
                dict(
                    name=name,
                    p=p,
                )
            )

            seen.add(tuple(path))

        cols.append(c)

    other_col: dict = dict(header="Other", vals=[], cells=[])
    for cat, stats in percentiles.items():
        for st, p in stats.items():
            if p is None:
                continue

            if (cat, st) in seen:
                continue

            name = _find_abbrv(config, [cat, st]) or st
            other_col["vals"].append(
                dict(
                    name=name,
                    p=p,
                )
            )

    cols.append(other_col)
    cols = [c for c in cols if len(c["vals"])]

    # Right-justify the percents (not necessarily the stat names)
    #    9% Pmit
    #   56% INT
    #   62% WIS
    for col in cols:
        p_strs = [f'{c["p"]:.0%}' for c in col["vals"]]
        max_width = max(len(x) for x in p_strs)
        col["cells"] = [
            f"{p_str:>{max_width}} {c['name']}" for p_str, c in zip(p_strs, col["vals"])
        ]

    # Format table
    hr_char = "-"
    vr_char = "|"
    padding = 1
    corner_char = "+"
    num_cols = len(cols)
    num_rows = max(len(c["cells"]) for c in cols)  # excludes header row

    col_widths = [
        max(max(len(cell) for cell in col["cells"]), len(col["header"])) for col in cols
    ]
    padding_str = " " * padding

    # width = content_width + padding_width + col_divider_width + table_border_width
    width = sum(col_widths) + (num_cols * 2 * padding) + (num_cols - 1) + 2
    height = num_rows + 3

    # "----------"
    hr = hr_char * width
    # "  ------  "
    hr = " " * (padding + 1) + hr[padding + 1 : -padding - 1] + " " * (padding + 1)
    # "+ ------ +"
    hr = corner_char + hr[1:-1] + corner_char

    rows = [hr]

    header_row = []
    for col, w in zip(cols, col_widths):
        header_row.append(f'{col["header"]:<{w}}')
    header_row = (padding_str + vr_char + padding_str).join(header_row)
    header_row = vr_char + padding_str + header_row + padding_str + vr_char
    rows.append(header_row)

    rows.append(hr)

    for y in range(num_rows):
        stat_row = []
        for x in range(num_cols):
            col = cols[x]
            w = col_widths[x]

            cell = col["cells"][y] if y < len(col["cells"]) else ""
            cell = f"{cell:<{w}}"
            stat_row.append(cell)

        stat_row = (padding_str + vr_char + padding_str).join(stat_row)
        stat_row = vr_char + padding_str + stat_row + padding_str + vr_char
        rows.append(stat_row)

    rows.append(hr)

    # Add header and codeblock wrapping
    msg = _get_header(info)
    msg += "\n" + "\n".join(rows)
    msg = f"```py\n{msg}\n```"

    return msg


def _find_abbrv(config: dict, stat_path: list[str]):
    return next(
        (
            x["alias"]
            for x in config["equip"]["abbreviations"]
            if x["stat_path"] == stat_path
        ),
        None,
    )


def _get_percentile(percentiles: dict, cat: str, stat: str) -> float | None:
    return percentiles.get(cat, dict()).get(stat, None)


def _get_header(info: dict):
    """
    @ Whatever nickname
    # (Legendary Charged Phase Gloves of Heimdall)
    # Level 500 • Tradeable • Owned by hujiko555
    """

    lines = []

    name: str = info["name"]
    if name.lower() == name:
        name = _capitalize_name(name)

    if info["alt_name"]:
        alt_name: str = info["alt_name"]
        if alt_name.lower() == alt_name:
            alt_name = _capitalize_name(alt_name)

        # @ Whatever nickname
        # # (Legendary Cobalt Power Gauntlets of Slaughter)
        lines.append(f"@ {alt_name}")
        lines.append(f"# ({name})")
    else:
        # @ Legendary Cobalt Power Gauntlets of Slaughter
        lines.append(f"@ {name}")

    # # Level 196 • Tradeable • Owned by Pickled_Cow
    if info["level"] == "Soulbound":
        status = "Soulbound"
    elif info["is_tradeable"]:
        status = f'Level {info["level"]} • Tradeable'
    else:
        status = f'Level {info["level"]} • Untradeable'
    status = status + " • " + f"Owned by {info['owner']['name']}"
    lines.append(f"# {status}")

    return "\n".join(lines)


def _capitalize_name(name: str):
    words = name.split()

    new_words = []
    for w in words:
        if w not in ["of", "the"]:
            new_words.append(w.capitalize())
        else:
            new_words.append(w)

    return " ".join(new_words)
