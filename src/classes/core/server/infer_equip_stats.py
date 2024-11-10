import json
import math

import loguru

from config import paths

LOGGER = loguru.logger.bind(tags=["equip_parser"])


def infer_equip_stats(
    equip: dict,
    ranges_override: dict | None = None,
):
    percentiles = _calc_all_percentiles(equip, ranges_override)
    legendary_percentiles = _calc_all_percentiles(
        equip, ranges_override, tier_override="Legendary"
    )

    return dict(
        percentiles=percentiles,
        legendary_percentiles=legendary_percentiles,
    )


def _calc_all_percentiles(
    equip: dict,
    ranges_override: dict | None = None,
    tier_override: str | None = None,
):
    if ranges_override is None:
        ranges = json.loads(paths.RANGES_FILE.read_text())
    else:
        ranges = ranges_override

    path_options = _enumerate_range_path_options_from_name(equip["name"])
    if tier_override:
        for p in path_options:
            p["quality"] = tier_override

    percentiles = dict()

    if equip["weapon_damage"]:
        base = equip["weapon_damage"]["damage"]["base"]
        real_base = _downgrade_stat("", "Attack Damage", base, equip)

        percentiles["weapon_damage"] = {
            "Attack Damage": _calc_percentile(
                ranges,
                path_options,
                "",
                "Attack Damage",
                real_base,
            ),
        }

    for cat, stats in equip["stats"].items():
        percentiles[cat] = dict()

        for st, d in stats.items():
            base = d["base"]
            real_base = _downgrade_stat(cat, st, base, equip)

            percentiles[cat][st] = _calc_percentile(
                ranges,
                path_options,
                cat,
                st,
                real_base,
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
    parts = [p for p in parts if p.lower() not in ["of", "the", "shield", "staff"]]
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
            for k2 in v:
                # Anything involving equip name needs to be case-insensitive to handle no-custom-font case
                if k2.lower() == k.lower():
                    v = v[k2]
                    break
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
        patt = req.replace("not!", "")

        result = patt.lower() == (value or "").lower()
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
    cat: str,
    stat: str,
    base_value: float,
) -> float | None:
    alias = stat
    if cat == "Damage Mitigations":
        if stat in ["Holy", "Dark", "Wind", "Elec", "Cold", "Fire"]:
            alias += " MIT"
    elif cat == "Spell Damage":
        alias += " EDB"

    for p in path_options:
        r = _find_min_max(ranges, p, alias)
        if not r:
            continue

        mn, mx = r
        if mn == mx:
            if mn == 0:
                return None

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

        # print("range", stat, base_value, mn, mx, p)
        return percentile

    # print("range_miss", stat, path_options)
    return None


def _downgrade_stat(cat: str, stat: str, base_value: float, equip: dict):
    if stat in ["Counter-Parry", "Counter-Resist"]:
        return _downgrade_counter_stat(stat, base_value, equip)
    else:
        return _downgrade_by_pxp(cat, stat, base_value, equip)


# based off LPR script and wiki page: https://ehwiki.org/wiki/The_Forge#Upgrade
def _downgrade_by_pxp(cat: str, stat: str, base_value: float, equip: dict) -> float:
    iw_coeff = _get_iw_coeff(cat, stat, equip)
    forge_coeff = _get_forge_coeff(cat, stat, equip)

    if equip["potency"]["tier"] == 0:
        pxp_zero = equip["potency"]["max_xp"]
    else:
        pxp_zero = _get_avg_pxp_zero(equip["name"])

    quality_bonus = (pxp_zero - 100) * (_get_pxp_multiplier(cat, stat) / 25)

    real_base = base_value
    real_base -= quality_bonus
    real_base /= forge_coeff * iw_coeff
    real_base += quality_bonus

    if real_base > base_value + 0.01:
        LOGGER.error(
            f"Base value increased after downgrades {cat} / {stat} {base_value:.3f} -> {real_base:.3f}"
        )

    # print(
    #     f"downgrade {stat=} {base_value=:.3f} {real_base=:.3f} {quality_bonus=:.3f} {forge_coeff=:.3f} {iw_coeff=:.3f}"
    # )

    return real_base


def _downgrade_counter_stat(stat: str, base_value: float, equip: dict) -> float:
    coeffs = {
        "Counter-Parry": dict(
            enchant="Overpower",
            mult=1.92,
        ),
        "Counter-Resist": dict(
            enchant="Penetrator",
            mult=4,
        ),
    }
    assert stat in coeffs

    c = coeffs[stat]
    lv = equip["enchants"].get(c["enchant"], 0)
    return base_value - lv * c["mult"]


def _get_avg_pxp_zero(name: str):
    avgs = {  # average PXP0 of various equips -- from LPR script
        "axe": 375,
        "club": 375,
        "rapier": 377,
        "shortsword": 377,
        "wakizashi": 378,
        "estoc": 377,
        "katana": 375,
        "longsword": 375,
        "mace": 375,
        "katalox staff": 368,
        "oak staff": 371,
        "redwood staff": 371,
        "willow staff": 371,
        "buckler": 374,
        "force shield": 374,
        "kite shield": 374,
        "phase": 377,
        "cotton": 377,
        "arcanist": 421,
        "shade": 394,
        "leather": 393,
        "power": 382,
        " plate": 377,
    }

    for key in avgs:
        if key.lower() in name.lower():
            if name.startswith("Peerless"):
                mult = 1
            elif name.startswith("Legendary"):
                mult = 0.95
            elif name.startswith("Magnificent"):
                mult = 0.89
            else:
                mult = 0.8

            return round(mult * avgs[key])
    else:
        LOGGER.warning(f"No average PXP0 for {name}")
        return 0


def _get_pxp_multiplier(cat: str, stat: str):
    alias = stat
    if cat == "Damage Mitigations":
        if stat in ["Holy", "Dark", "Wind", "Elec", "Cold", "Fire"]:
            alias += " MIT"
    elif cat == "Spell Damage":
        alias += " EDB"

    mults = {
        "Attack Damage": 0.0854,
        "Attack Crit Chance": 0.0105,
        "Attack Crit Damage": 0.01,
        "Attack Accuracy": 0.06069,
        "Attack Speed": 0.0481,
        "Magic Damage": 0.082969,
        "Magic Crit Chance": 0.0114,
        "Spell Crit Damage": 0.01,
        "Magic Accuracy": 0.0491,
        "Casting Speed": 0.0489,
        "Strength": 0.03,
        "Dexterity": 0.03,
        "Endurance": 0.03,
        "Agility": 0.03,
        "Intelligence": 0.03,
        "Wisdom": 0.03,
        "Evade Chance": 0.025,
        "Resist Chance": 0.0804,
        "Physical Mitigation": 0.021,
        "Magical Mitigation": 0.0201,
        "Block Chance": 0.0998,
        "Parry Chance": 0.0894,
        "Mana Conservation": 0.1,
        "Crushing": 0.0155,
        "Slashing": 0.0153,
        "Piercing": 0.015,
        "Burden": 0,
        "Interference": 0,
        "Elemental": 0.0306,
        "Divine": 0.0306,
        "Forbidden": 0.0306,
        "Deprecating": 0.0306,
        "Supportive": 0.0306,
        "Holy EDB": 0.0804,
        "Dark EDB": 0.0804,
        "Wind EDB": 0.0804,
        "Elec EDB": 0.0804,
        "Cold EDB": 0.0804,
        "Fire EDB": 0.0804,
        "Holy MIT": 0.1,
        "Dark MIT": 0.1,
        "Wind MIT": 0.1,
        "Elec MIT": 0.1,
        "Cold MIT": 0.1,
        "Fire MIT": 0.1,
        "Counter-Resist": 0.1,
    }

    if alias in mults:
        return mults[alias]
    else:
        LOGGER.warning(f"No base multiplier for {cat} / {stat}")
        return 1


# https://ehwiki.org/wiki/Item_World#Potencies
def _get_iw_coeff(cat: str, stat: str, equip: dict):
    enchants = equip["enchants"]

    coeff = 1
    if cat == "Damage Mitigations":
        match stat:
            case "Cold":
                coeff += 0.04 * enchants.get("Coldproof", 0)
            case "Dark":
                coeff += 0.04 * enchants.get("Darkproof", 0)
            case "Elec":
                coeff += 0.04 * enchants.get("Elecproof", 0)
            case "Fire":
                coeff += 0.04 * enchants.get("Fireproof", 0)
            case "Holy":
                coeff += 0.04 * enchants.get("Holyproof", 0)
            case "Wind":
                coeff += 0.04 * enchants.get("Windproof", 0)
            case _:
                pass
    elif stat == "HP Bonus":
        coeff += 0.02 * enchants.get("Juggernaut", 0)
    elif stat == "MP Bonus":
        coeff += 0.02 * enchants.get("Capacitor", 0)
    elif stat == "Attack Damage":
        coeff += 0.02 * enchants.get("Butcher", 0)
    elif stat == "Magic Damage":
        coeff += 0.02 * enchants.get("Archmage", 0)
    elif stat == "Attack Crit Chance":
        coeff += 0.02 * enchants.get("Fatality", 0)
    elif stat == "Spell Crit Damage":
        coeff += 0.02 * enchants.get("Annihilator", 0)
    elif stat == "Attack Speed":
        coeff += 0.0192 * enchants.get("Swift Strike", 0)
    elif stat == "Casting Speed":
        coeff += 0.014675 * enchants.get("Spellweaver", 0)
    elif stat == "Counter-Parry":
        coeff += 0.04 * enchants.get("Overpower", 0)
    elif stat == "Counter-Resist":
        coeff += 0.04 * enchants.get("Penetrator", 0)
    elif stat == "Mana Conservation":
        coeff += 0.05 * enchants.get("Economizer", 0)

    return coeff


# https://ehwiki.org/wiki/The_Forge#Bindings
def _get_forge_coeff(cat: str, stat: str, equip: dict):
    upgrades = equip["upgrades"]

    if stat in ["Attack Damage", "Magic Damage"]:
        level_mult = 0.279575
    else:
        level_mult = 0.2

    level = 0
    if stat == "Attack Damage":
        level = upgrades.get("Physical Damage", 0)
    elif stat == "Magic Damage":
        level = upgrades.get("Magical Damage", 0)
    elif stat == "Attack Accuracy":
        level = upgrades.get("Physical Hit Chance", 0)
    elif stat == "Magic Accuracy":
        level = upgrades.get("Magical Hit Chance", 0)
    elif stat == "Attack Crit Chance":
        level = upgrades.get("Physical Crit Chance", 0)
    elif stat == "Magic Crit Chance":
        level = upgrades.get("Magical Crit Chance", 0)
    elif stat == "Physical Mitigation":
        level = upgrades.get("Physical Defense", 0)
    elif stat == "Magical Mitigation":
        level = upgrades.get("Magical Defense", 0)
    elif stat == "Evade Chance":
        level = upgrades.get("Evade Chance", 0)
    elif stat == "Block Chance":
        level = upgrades.get("Block Chance", 0)
    elif stat == "Parry Chance":
        level = upgrades.get("Parry Chance", 0)
    elif stat == "Resist Chance":
        level = upgrades.get("Resist Chance", 0)
    #
    elif cat == "Damage Mitigations":
        level = upgrades.get(stat + " Mitigation", 0)
    elif cat == "Primary Attributes":
        level = upgrades.get(stat + " Bonus", 0)
    elif cat == "Spell Damage":
        level = upgrades.get(stat + " Spell Damage", 0)
    elif cat == "Proficiency":
        level = upgrades.get(stat + " Proficiency", 0)

    return 1 + level_mult * math.log(0.1 * level + 1)
