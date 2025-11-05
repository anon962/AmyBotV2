def parse_equip_name(name: str) -> dict:
    rem = name.lower().strip()

    try:
        tier, rem = _find(rem, _TIERS, raise_on_missing=True)
        prefix, rem = _find(rem, _PREFIXES)
        type, rem = _find(rem, _TYPES, raise_on_missing=True)
        suf_art, rem = _find(rem, _SUFFIX_ARTICLES)
        suffix, rem = _find(rem, _SUFFIXES)
    except:
        raise Exception((name, rem))

    assert len(rem) == 0, (name, rem)

    return dict(
        tier=tier,
        prefix=prefix,
        type=type,
        suf_art=suf_art,
        suffix=suffix,
    )


def _find(rem: str, opts: list[str], raise_on_missing=False):
    for o in opts:
        if rem.startswith(o.lower()):
            return o, rem[len(o) :].strip()
    else:
        if raise_on_missing:
            raise ValueError
        else:
            return None, rem.strip()


_TIERS = [
    "Crude",
    "Fair",
    "Average",
    "Superior",
    "Exquisite",
    "Magnificent",
    "Legendary",
    "Peerless",
]


_PREFIXES = [
    "Onyx",
    "Mithril",
    "Ruby",
    "Jade",
    "Zircon",
    "Cobalt",
    "Amber",
    #
    "Shielding",
    "Agile",
    "Reinforced",
    "Savage",
    "Frugal",
    "Charged",
    "Radiant",
    "Mystic",
    #
    "Tempestuous",
    "Shocking",
    "Fiery",
    "Hallowed",
    "Ethereal",
    "Arctic",
    "Demonic",
]

_TYPES = [
    "Kevlar Helmet",
    "Kevlar Breastplate",
    "Kevlar Gauntlets",
    "Kevlar Boots",
    "Kevlar Leggings",
    #
    "Shade Helmet",
    "Shade Boots",
    "Shade Leggings",
    "Shade Breastplate",
    "Shade Gauntlets",
    #
    "Leather Helmet",
    "Leather Boots",
    "Leather Leggings",
    "Leather Breastplate",
    "Leather Gauntlets",
    #
    "Power Helmet",
    "Power Leggings",
    "Power Gauntlets",
    "Power Boots",
    "Power Armor",
    #
    "Plate Sabatons",
    "Plate Greaves",
    "Plate Cuirass",
    "Plate Helmet",
    "Plate Gauntlets",
    #
    "Reactive Sabatons",
    "Reactive Greaves",
    "Reactive Cuirass",
    "Reactive Helmet",
    "Reactive Gauntlets",
    #
    "Willow Staff",
    "Redwood Staff",
    "Oak Staff",
    "Ebony Staff",
    "Katalox Staff",
    #
    "Chain Helmet",
    "Chain Sabatons",
    "Chain Cuirass",
    "Chain Greaves",
    "Chain Gauntlets",
    #
    "Force Shield",
    "Tower Shield",
    "Kite Shield",
    "Buckler",
    #
    "Cotton Cap",
    "Cotton Robe",
    "Cotton Gloves",
    "Cotton Pants",
    "Cotton Shoes",
    #
    "Phase Cap",
    "Phase Robe",
    "Phase Gloves",
    "Phase Pants",
    "Phase Shoes",
    #
    "Gossamer Cap",
    "Gossamer Robe",
    "Gossamer Gloves",
    "Gossamer Pants",
    "Gossamer Shoes",
    #
    "Ironsilk Gloves",
    "Ironsilk Cap",
    "Ironsilk Shoes",
    "Ironsilk Pants",
    "Ironsilk Robe",
    #
    "Drakehide Gauntlets",
    "Drakehide Helmet",
    "Drakehide Boots",
    "Drakehide Breastplate",
    "Drakehide Leggings",
    #
    "Axe",
    "Scythe",
    "Shortsword",
    "Swordchucks",
    "Katana",
    "Dagger",
    "Wakizashi",
    "Longsword",
    "Estoc",
    "Rapier",
    "Club",
    "Great Mace",
    "Mace",
]

_SUFFIX_ARTICLES = [
    "of the",
    "of",
    "the",
]

_SUFFIXES = [
    "Negation",
    "Protection",
    "Frost-born",
    "Wind-waker",
    "Destruction",
    "Thunder-child",
    "Warding",
    "Spirit-ward",
    "Fire-eater",
    "Balance",
    "Slaughter",
    "Deflection",
    "Dampening",
    "Stoneskin",
    "Earth-walker",
    "Elementalist",
    "Cheetah",
    "Thrice-blessed",
    "Fleet",
    "Focus",
    "Heaven-sent",
    "Demon-fiend",
    "Curse-weaver",
    "Owl",
    "Barrier",
    "Swiftness",
    "Turtle",
    "Vampire",
    "Stoneskin",
    "Raccoon",
    "Arcanist",
    "Fox",
    "Banshee",
    "Illithid",
    "Battlecaster",
    "Ox",
    "Nimble",
    "Shadowdancer",
    #
    "Mjolnir",
    "Fenrir",
    "Freyr",
    "Niflheim",
    "Heimdall",
    "Surtr",
]
