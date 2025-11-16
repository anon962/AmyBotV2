import json

from config.paths import DATA_DIR

groups = [
    [
        # "Cotton Cap",
        # "Cotton Robe",
        # "Cotton Gloves",
        # "Cotton Pants",
        "Cotton Shoes",
    ],
    [
        # "Leather Helmet",
        # "Leather Breastplate",
        # "Leather Gauntlets",
        # "Leather Leggings",
        "Leather Boots",
    ],
    [
        # "Plate Helmet",
        # "Plate Cuirass",
        # "Plate Gauntlets",
        # "Plate Greaves",
        "Plate Sabatons",
    ],
]

tiers = [
    "Crude",
    "Fair",
    "Average",
    "Superior",
    "Magnificent",
    "Legendary",
    "Peerless",
]

lines = []
ranges = json.loads((DATA_DIR / "ranges.json").read_text())
for grp in groups:
    series_name = grp[0].split()[0]
    series = ranges[series_name]

    for type in grp:
        ln = [type]
        loc = type.split()[1]
        for tier in tiers:
            try:
                r = series[loc][tier]["Endurance"]["all | all"]
                ln.append(str(r["min"]))
                ln.append(str(r["max"]))
            except KeyError:
                ln.append("0")
                ln.append("0")

        lines.append(ln)

print("\n".join(",".join(x) for x in zip(*lines)))
