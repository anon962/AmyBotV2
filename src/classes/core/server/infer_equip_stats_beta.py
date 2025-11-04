import loguru

LOGGER = loguru.logger.bind(tags=["equip_parser"])

_TIER_RANGES = dict(
    Crude=(1, 30),
    Fair=(30, 70),
    Average=(60, 100),
    Superior=(90, 130),
    Exquisite=(120, 160),
    Magnificent=(150, 180),
    Legendary=(170, 200),
    Peerless=(200, 200),
)


def infer_equip_stats(
    equip: dict,
):
    percentiles = _calc_all_percentiles(equip)
    legendary_percentiles = _calc_all_percentiles(equip, as_legendary=True)

    return dict(
        percentiles=percentiles,
        legendary_percentiles=legendary_percentiles,
    )


@LOGGER.catch(reraise=True)
def _calc_all_percentiles(
    equip: dict,
    as_legendary=False,
):
    percentiles = dict()

    mn, mx = _TIER_RANGES[equip["name_parts"]["tier"]]
    if as_legendary:
        mn, mx = _TIER_RANGES["Legendary"]
    ivl_length = mx - mn

    if equip["weapon_damage"] and equip["weapon_damage"]["Attack Damage"]:
        base = equip["weapon_damage"]["Attack Damage"]["base"]
        percentiles["weapon_damage"] = {"Attack Damage": (base - mn) / ivl_length}

    for cat, stats in equip["stats"].items():
        percentiles[cat] = dict()

        for st, d in stats.items():
            if d["base"] == 0:
                continue

            if ivl_length > 0:
                percentiles[cat][st] = (d["base"] - mn) / ivl_length
            else:
                percentiles[cat][st] = 1

    return percentiles
