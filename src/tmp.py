import asyncio
import json
import math
import random
import statistics
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from inspect import signature
from typing import TypeAlias, TypeVar

import numpy
import pandas
import plotly.express as px
import plotly.graph_objects as go
import scipy
import scipy.optimize
import torch

from classes.core.server.parse_equip_name import SLOT_LOCS, parse_equip_name
from classes.db import init_db
from config.paths import DATA_DIR

warnings.filterwarnings("ignore")

WORLD = "isekai"
# WORLD = "persistent"

# FIT_TYPE = "curved"
# FIT_TYPE = "plane"
# FIT_TYPE = "wiki"
FIT_TYPE = "wiki2"

MIN_RESULT_COUNT = 5 if WORLD == "isekai" else 60


async def main():
    edb = init_db()

    tmp(edb)
    return

    counts = tally(edb)

    tmp_dir = DATA_DIR / "tmp"
    tmp_dir.mkdir(exist_ok=True)

    for fp in tmp_dir.glob("*"):
        fp.unlink()

    items = list(counts.items())
    # items.sort(key=lambda kv: len(kv[1]), reverse=True)
    # items.sort(key=lambda kv: (kv[0][0], len(kv[1])))
    items.sort(
        key=lambda kv: (
            kv[1][0]["name_parts"]["type"].split()[0],
            kv[1][0]["stat_name"],
        )
    )

    # plots
    missing_filters = set()
    results: list = []
    for gid, group in items:
        if len(group) < MIN_RESULT_COUNT:
            continue

        affix_filters = []
        match gid[0]:
            case "Physical Mitigation":
                affix_filters = ["Protection"]
            case "Magical Mitigation":
                affix_filters = ["Warding"]
            case "Block":
                affix_filters = ["Shielding", "Barrier"]
            case "Parry":
                affix_filters = ["Nimble"]
            case "Attack Crit Damage":
                affix_filters = ["Balance", "Savage"]
            case "Attack Accuracy":
                affix_filters = ["Balance"]
            case "Magic Damage":
                affix_filters = ["Radiant", "Destruction"]
            case "Magic Accuracy":
                affix_filters = ["Focus"]
            case "Evade Chance":
                affix_filters = ["Fleet"]
            case "Burden":
                affix_filters = ["Mithril"]
            case "Interference":
                affix_filters = ["Mithril"]
            case "Crushing":
                affix_filters = ["Dampening", "Reinforced"]
            case "Piercing":
                affix_filters = ["Deflection", "Reinforced"]
            case "Slashing":
                affix_filters = ["Stoneskin", "Reinforced"]
            case "Strength":
                affix_filters = ["Ox"]
            case "Dexterity":
                affix_filters = ["Raccoon"]
            case "Endurance":
                affix_filters = ["Turtle"]
            case "Agility":
                affix_filters = ["Cheetah"]
            case "Wisdom":
                affix_filters = ["Owl"]
            case "Intelligence":
                affix_filters = ["Fox"]
            case "Divine":
                affix_filters = ["Heaven-sent"]
            case "Elemental":
                affix_filters = ["Elementalist"]
            case "Deprecating":
                affix_filters = ["Curse-weaver"]
            case "Supportive":
                affix_filters = ["Earth-walker"]
            case "Divine":
                affix_filters = ["Heaven-sent"]
            case "Fire EDB":
                # affix_filters = ["Surtr"]
                pass
            case "Wind EDB":
                # affix_filters = ["Freyr"]
                pass
            case "Elec EDB":
                # affix_filters = ["Mjolnir"]
                pass
            case "Holy EDB":
                # affix_filters = ["Heimdall"]
                pass
            case "Dark EDB":
                # affix_filters = ["Fenrir"]
                pass
            case "Cold EDB":
                # affix_filters = ["Niflheim"]
                pass
            case "Attack Damage":
                affix_filters = ["Savage", "Slaughter"]
                pass
            case _:
                missing_filters.add(gid[0])
                continue

        STAT_FILTERS = [
            # "Block",
            # "Parry",
            # "Magical Mitigation",
            # "Physical Mitigation",
            # "Strength",
            # "Dexterity",
            # "Intelligence",
            # "Fire EDB",
            # "Wind EDB",
            # "Elec EDB",
            # "Holy EDB",
            # "Dark EDB",
            # "Cold EDB",
            "Attack Damage",
        ]
        if STAT_FILTERS and gid[0] not in STAT_FILTERS:
            continue

        loc_mult = 1
        if False:
            pass
        if group[0]["name_parts"]["type"] in SLOT_LOCS["HEAD"]:
            loc_mult = 1.26
        elif group[0]["name_parts"]["type"] in SLOT_LOCS["BODY"]:
            loc_mult = 1.51333
        elif group[0]["name_parts"]["type"] in SLOT_LOCS["HANDS"]:
            loc_mult = 1.13555
        elif group[0]["name_parts"]["type"] in SLOT_LOCS["LEGS"]:
            loc_mult = 1.386666
        elif group[0]["name_parts"]["type"] in SLOT_LOCS["FEET"]:
            loc_mult = 1
        else:
            continue

        group = [
            x
            for x in group
            if x["name_parts"]["suffix"] not in affix_filters
            and x["name_parts"]["prefix"] not in affix_filters
        ]
        if len(group) < MIN_RESULT_COUNT:
            continue

        name = "_".join(str(x) for x in gid)
        print(f"{len(group)}x", name)

        best: tuple = None  # type: ignore
        for _ in range(100):
            pts = [(x["base"], x["d"]["level"], x["value"]) for x in group]
            # start = random.random() * 100

            try:
                if FIT_TYPE == "curved":
                    fit = CurvedPlaneFit.from_points(pts)
                elif FIT_TYPE == "wiki":
                    fit = WikiFit.from_points(pts)
                elif FIT_TYPE == "wiki2":
                    match gid[0]:
                        case (
                            "Agility"
                            | "Strength"
                            | "Dexterity"
                            | "Endurance"
                            | "Intelligence"
                            | "Wisdom"
                        ):
                            denom = 35.7143
                        case "Parry" | "Block":
                            denom = 200
                        case "Attack Accuracy" | "Magic Accuracy":
                            denom = 50
                        case (
                            "Crushing"
                            | "Piercing"
                            | "Slashing"
                            | "Interference"
                            | "Burden"
                        ):
                            denom = 999_999
                        case "Physical Mitigation" | "Magical Mitigation":
                            denom = 2000
                        case (
                            "Fire EDB"
                            | "Wind EDB"
                            | "Elec EDB"
                            | "Holy EDB"
                            | "Dark EDB"
                            | "Cold EDB"
                        ):
                            denom = 200
                        case "Attack Damage":
                            denom = 16.6
                        case _:
                            print("No denom for:", gid[0])
                            break

                    fit = WikiFit2.from_points(pts, denom, loc_mult)
                else:
                    fit = PlaneFit.from_points(pts)
            except Exception:
                # import traceback

                # traceback.print_exc()
                continue

            loss = fit.calc_loss(pts)

            if not best or loss < best[0]:
                best = (loss, fit)

        if not best:
            print("\tFailed to fit")
            continue

        loss, fit = best
        print(
            "\tloss:",
            pp(loss),
            "mean:",
            pp(statistics.mean([x["value"] for x in group])),
        )
        print("\tfit:", str(fit))

        results.append((fit, group[0], loss))
        plot(name, group, fit, loss)

    print(f"Missing filters for:", missing_filters)

    plot_all_fits(*zip(*results))


def tmp(edb):
    def dump(name: str, pts: list[tuple[float, float]]):
        pts_str = ",".join(f"({pt[0]},{pt[1]})" for pt in pts)
        print(
            f"""
            {name}=[{pts_str}]
            """.strip()
        )

    # armor_type = "leather"
    # slots = [
    #     "boots",
    #     "leggings",
    #     "gauntlets",
    #     "breastplate",
    #     "helmet",
    # ]
    armor_type = "plate"
    slots = [
        "sabatons",
        "greaves",
        "gauntlets",
        "cuirass",
        "helmet",
    ]

    def select(name):
        stats = dict()

        rs = edb.execute(
            f"""
            SELECT data FROM equips
            WHERE is_isekai = 1
            AND JSON_EXTRACT(data, '$.owner.name') IS NOT NULL
            AND JSON_EXTRACT(data, '$.name') LIKE '%{name}%'
            AND JSON_EXTRACT(data, '$.level') = 'Unassigned'
            AND updated_at > '2025-11-05T13'
            -- AND updated_at < '2025-11-05T13'
            """
        ).fetchall()

        for r in rs:
            d = json.loads(r["data"])

            for cat_name, cat in d["stats"].items():
                for stat_name, stat in cat.items():
                    stats.setdefault(stat_name, dict())

                    s = dict(
                        stat_name=stat_name,
                        base=stat["base"] / 2,
                        value=stat["value"],
                        name=d["name"],
                    )

                    old = stats[stat_name].get(s["base"], dict()).get("value", None)
                    if old and s["value"] > old:
                        continue

                    stats[stat_name][s["base"]] = s

        result = dict()
        for stat_name, by_base in stats.items():
            as_list = sorted(list(by_base.values()), key=lambda x: x["base"])
            result[stat_name] = as_list

        return result

    for eq in [
        # dict(key="h_n", name="Plate Cuirass", stat="Physical Mitigation", filter="Protection"),
        # dict(key="h_r", name="Power Armor", stat="Physical Mitigation", filter="Protection"),
        # dict(key="m_n", name="Leather Breastplate", stat="Physical Mitigation", filter="Protection"),
        # dict(key="m_r", name="Shade Breastplate", stat="Physical Mitigation", filter="Protection"),
        # dict(key="l_n", name="Cotton Robe", stat="Physical Mitigation", filter="Protection"),
        # dict(key="l_r", name="Phase Robe", stat="Physical Mitigation", filter="Protection"),
        # 
        # dict(key="h_n", name="Plate Cuirass", stat="Endurance", filter="Turtle"),
        # dict(key="h_r", name="Power Armor", stat="Endurance", filter="Turtle"),
        # dict(key="m_n", name="Leather Breastplate", stat="Endurance", filter="Turtle"),
        # dict(key="m_r", name="Shade Breastplate", stat="Endurance", filter="Turtle"),
        # dict(key="l_n", name="Cotton Robe", stat="Endurance", filter="Turtle"),
        # dict(key="l_r", name="Phase Robe", stat="Endurance", filter="Turtle"),
        # 
        # dict(key="l_n", name="Cotton Shoes", stat="Physical Mitigation", filter="Protection"),
        dict(key="l_n", name="Leather Boots", stat="Endurance", filter="Turtle"),
        dict(key="l_n", name="Plate Sabatons", stat="Endurance", filter="Turtle"),
        dict(key="l_n", name="Plate Sabatons", stat="Strength", filter="Turtle"),
        dict(key="l_n", name="Plate Sabatons", stat="Dexterity", filter="Turtle"),
    ]: # fmt: skip
        vals = select(eq["name"])
        vals = vals.get(eq["stat"], [])
        vals = [v for v in vals if eq["filter"] not in v["name"]]
        dump(eq["key"], [(v["base"], v["value"]) for v in vals])

    # for idx, slot in enumerate(slots):
    #     vals = select(f"{armor_type} {slot}")
    #     vals = vals['Physical Mitigation']
    #     vals = [v for v in vals if "Protection" not in v["name"]]
    #     dump(f"p_{{{idx}}}", [(v['base'], v['value']) for v in vals])
    # for idx in range(len(slots)):
    #     print(
    #         rf"p_{{{idx}}}.y\ \sim\ a_{{p}}b\left(c_{{p}}\cdot p_{{{idx}}}.x+1\right)^{{1.5}}"
    #     )

    # for idx, slot in enumerate(slots):
    #     vals = select(f"{armor_type} {slot}")
    #     vals = vals['Magical Mitigation']
    #     vals = [v for v in vals if "Warding" not in v["name"]]
    #     dump(f"p_{{{idx}}}", [(v['base'], v['value']) for v in vals])
    # for idx in range(len(slots)):
    #     print(
    #         rf"m_{{{idx}}}.y\ \sim\ a_{{m}}b\left(c_{{m}}\cdot m_{{{idx}}}.x+1\right)^{{1.5}}"
    #     )


def tmp2(edb):
    rs = edb.execute(
        """
        SELECT data FROM equips
        WHERE is_isekai = 1
        """
    ).fetchall()

    acc = dict()

    for r in rs:
        d = json.loads(r["data"])

        name_parts = parse_equip_name(d["name"])

        level = 1 if d["level"] == "Unassigned" else d["level"]
        if level == "Soulbound":
            continue

        for cat_name, cat in d["stats"].items():
            for stat_name, stat in cat.items():
                k = (stat_name, name_parts["type"], stat["base"])
                if stat["base"] == 0:
                    continue

                acc.setdefault(k, dict())
                a = acc[k]

                a[level] = dict(
                    stat_name=stat_name,
                    type=name_parts["type"],
                    suffix=name_parts["suffix"],
                    prefix=name_parts["prefix"],
                    level=level,
                    base=stat["base"],
                    value=stat["value"],
                )

    vss = [list(vs.values()) for vs in acc.values()]
    vss.sort(key=lambda vs: len(vs), reverse=True)
    print(len(vss[0]), vss[0][0])

    for vs in vss[:10]:
        print(vs[0]["stat_name"], vs[0]["type"], vs[0]["base"])
        vs.sort(key=lambda v: v["level"])

        for v in vs:
            print(
                ", ".join(
                    [
                        str(v["base"]),
                        str(v["level"]),
                        str(v["value"]),
                        (v["prefix"] or "") + "|" + (v["suffix"] or ""),
                    ]
                )
            )

        print("---")
        # break


def plot(name: str, group: list[dict], fit: "Fit", loss: float):
    lines = []
    lines.append(f"{fit.__class__} {loss} | {repr(fit)}")

    equip_url = "https://hentaiverse.org/"
    if WORLD == "isekai":
        equip_url += "isekai/"
    equip_url += "equip/"

    data = []
    annotations = []
    for v in group:
        pred = fit.eval(v["base"], v["d"]["level"])
        loss = abs((v["value"] - pred) / v["value"])

        d = dict(
            base=v["base"],
            level=v["d"]["level"],
            value=v["value"],
            name=v["d"]["name"],
            suffix=v["name_parts"]["suffix"],
            pred=pred,
            loss=loss,
        )
        data.append(d)

        if loss > 0.01:
            annotations.append(
                dict(
                    x=v["base"],
                    y=v["d"]["level"],
                    z=v["value"],
                    text=f"""<a href="{equip_url}{v['d']['id']}/{v['d']['key']}">link</a>""",
                    showarrow=False,
                )
            )

        lines.append(
            ",".join(
                str(x)
                for x in [
                    v["base"],
                    v["d"]["level"],
                    v["value"],
                    v["name_parts"]["tier"],
                    f"{equip_url}{v['d']['id']}/{v['d']['key']}",
                ]
            )
        )

    df = pandas.DataFrame(data)
    fig = px.scatter_3d(
        df,
        x="base",
        y="level",
        z="value",
        color="loss",
        hover_data=list(data[0].keys()),
    )

    fig.update_layout(
        scene=dict(
            annotations=annotations,
        ),
    )
    fig.update_traces(
        # marker_size=8,
    )

    min_base = min(v["base"] for v in group) - 1e-3
    max_base = max(v["base"] for v in group)
    x = numpy.arange(min_base * 0.9, max_base * 1.1, (max_base - min_base) / 100)

    min_level = min(v["d"]["level"] for v in group) - 1e-3
    max_level = max(v["d"]["level"] for v in group)
    y = numpy.arange(min_level * 0.9, max_level * 1.1, (max_level - min_level) / 100)

    X, Y = numpy.meshgrid(x, y)
    Z = fit.eval(X, Y)

    surface = go.Surface(
        x=X,
        y=Y,
        z=Z,
        showscale=False,
        opacity=0.3,
        showlegend=False,
        hoverinfo="skip",
        hovertemplate=None,
    )
    surface.contours.x.highlight = False  # type: ignore
    surface.contours.y.highlight = False  # type: ignore
    surface.contours.z.highlight = False  # type: ignore
    fig.add_trace(surface)

    fig.write_html(DATA_DIR / "tmp" / f"{name}.html")

    (DATA_DIR / "tmp" / f"{name}.data").write_text("\n".join(lines))


def plot_all_fits(fits: "tuple[Fit]", samples: tuple[dict], loss: tuple[float]):
    bad_count = 0

    data = []
    for idx, f in enumerate(fits):
        l = loss[idx]
        if math.isnan(l):
            bad_count += 1
            continue

        x = f.params[0]

        if len(f.params) > 1:
            y = f.params[1]
        else:
            y = 0

        if len(f.params) > 2:
            z = f.params[2]
        else:
            z = 0

        if any(u > 100_000 for u in [x, y, z]):
            continue

        s = samples[idx]
        data.append(
            dict(
                label="_".join(
                    (
                        s["stat_name"],
                        s["name_parts"]["type"],
                    )
                ),
                x=x,
                y=y,
                z=z,
                loss=l,
                slot=next(
                    kv[0]
                    for kv in SLOT_LOCS.items()
                    if s["name_parts"]["type"] in kv[1]
                ),
            )
        )

    while True:
        to_remove = None

        mean = [statistics.mean([d[k] for d in data]) for k in ["x", "y", "z"]]
        stdev = [statistics.stdev([d[k] for d in data]) for k in ["x", "y", "z"]]
        for d in data:
            for idx, k in enumerate(["x", "y", "z"]):
                if (
                    d[k] < mean[idx] - 4 * stdev[idx]
                    or d[k] > mean[idx] + 4 * stdev[idx]
                ):
                    to_remove = d
                    break
            if to_remove:
                break

        if to_remove:
            data = [d for d in data if d is not to_remove]
            bad_count += 1
        else:
            break

    print(f"Ignored {bad_count} / {len(data) + bad_count} param samples")

    print("avg loss:", statistics.mean(loss))

    for d in data:
        num_neighbors = len(
            [
                d2
                for d2 in data
                if 10
                > math.sqrt(
                    (d["x"] - d2["x"]) ** 2
                    + (d["y"] - d2["y"]) ** 2
                    + (d["z"] - d2["z"]) ** 2
                )
            ]
        )
        d["size"] = math.sqrt(num_neighbors)

    df = pandas.DataFrame(data)
    fig = px.scatter_3d(
        df,
        x="x",
        y="y",
        z="z",
        # color="loss",
        color="slot",
        size="size",
        hover_data=list(data[0].keys()),
    )

    fig.write_html(DATA_DIR / "tmp" / f"000_params.html")


def tally(edb):
    if WORLD == "isekai":
        rs = edb.execute(
            """
            SELECT id, key, data
            FROM equips
            WHERE is_isekai = 1
            AND JSON_EXTRACT(data, '$.owner.name') IS NOT NULL
            AND updated_at > '2025-11-05T13'
            """
        )
    else:
        rs = edb.execute(
            """
            SELECT id, key, data
            FROM equips
            WHERE is_isekai = 0
            AND json_extract(data, '$.upgrades') == '{}'
            AND json_extract(data, '$.enchants') == '{}'
            """
        )

    data = []
    for r in rs:
        d = json.loads(r["data"])
        data.append(d)

        d["id"] = r["id"]
        d["key"] = r["key"]

    counts = dict()
    seen = set()
    for d in data:
        if d["id"] in seen:
            continue
        seen.add(d["id"])

        if d["level"] == "Unassigned":
            d["level"] = 1
        if not isinstance(d["level"], int):
            continue
        # if d["level"] >= 50:
        #     continue

        for cat_name, cat in d["stats"].items():
            for stat_name, stat in cat.items():
                if cat_name == "Spell Damage":
                    stat_name += " EDB"

                # if stat_name != "Crushing":
                #     continue
                if stat["base"] == 0:
                    continue

                try:
                    name_parts = parse_equip_name(d["name"])
                except Exception:
                    print("Bad name", d["name"])
                    continue

                key = (
                    stat_name,
                    # int(d["level"] / 50),
                    # stat["base"] / 10,
                    # d["level"],
                    # name_parts["tier"],
                    # name_parts["prefix"],
                    name_parts["type"],
                    # name_parts["suffix"],
                )
                counts.setdefault(key, [])
                counts[key].append(
                    dict(
                        stat_name=stat_name,
                        base=stat["base"],
                        value=stat["value"],
                        name_parts=name_parts,
                        d=d,
                    )
                )

    # debug
    items = counts.items()
    items = sorted(items, key=lambda kv: len(kv[1]))

    kpads = [
        max(len(str(k[idx] or "")) for k, cs in items)
        for idx in range(len(items[0][0]))
    ]
    for k, vs in items:
        if len(vs) < MIN_RESULT_COUNT:
            continue

        vs = sorted([v["base"] for v in vs], key=lambda v: v)
        vs = list(vs)

        pad = lambda s, n: f"{s or '':<{n}}"
        print(
            f"{len(vs):<5}",
            f"{vs[0]:<6.1f}",
            f"{vs[-1]:<6.1f}",
            *[pad(pt, kpads[idx] + 3) for idx, pt in enumerate(k)],
        )

    return counts


Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

T = TypeVar("T")


@dataclass
class Fit(ABC):
    params: list[float]

    @staticmethod
    @abstractmethod
    def _eval(x: T, y: T, *params) -> T: ...

    @classmethod
    def from_points(cls, pts: list[Point3]):
        def eval(pts, *args):
            return cls._eval(pts[:, 0], pts[:, 1], *args)

        arr = numpy.array(pts, dtype=numpy.float64)
        result: tuple = scipy.optimize.curve_fit(
            eval,
            arr[:, :2],
            arr[:, 2],
            tuple(
                random.choice([0, 10, 100])
                for _ in range(len(signature(cls._eval).parameters) - 2)
            ),
            # bounds=(0, numpy.inf),
        )

        return cls(result[0])

    def eval(self, x, y):
        return self._eval(x, y, *self.params)

    def eval_all(self, xys: list[Point2]) -> list[float]:
        xs = torch.tensor([u[0] for u in xys])
        ys = torch.tensor([u[1] for u in xys])
        zs = self.eval(xs, ys)
        return zs.tolist()

    def calc_loss(self, xyzs: list[tuple[float, float, float]]) -> float:
        zs = torch.tensor([u[2] for u in xyzs])
        preds = torch.tensor(self.eval_all([(u[0], u[1]) for u in xyzs]))

        loss = ((preds - zs) / zs).abs()
        loss = loss.mean()
        loss = loss.item()
        return loss

    def __str__(self) -> str:
        return " ".join([pp(p, 5) for p in self.params])

    def __repr__(self) -> str:
        return " ".join([str(p) for p in self.params])


@dataclass
class PlaneFit(Fit):
    @staticmethod
    def _eval(x, y, a, b, c, k):
        return (a * x + b * y + k) / (-c + 1e-9)

    @classmethod
    def from_points(cls, pts: list[Point3]) -> "PlaneFit":
        p0, p1, p2 = pts

        u = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        v = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])

        cross = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )

        k = -1 * (cross[0] * p0[0] + cross[1] * p0[1] + cross[2] * p0[2])

        return cls([cross[0], cross[1], cross[2], k])

    def __str__(self) -> str:
        return " ".join(
            [
                pp(self.params[0] / (-self.params[2] + 1e-9)),
                pp(self.params[1] / (-self.params[2] + 1e-9)),
                pp(self.params[3] / (-self.params[2] + 1e-9)),
            ]
        )

    def __repr__(self) -> str:
        return " ".join(
            [
                str(self.params[0] / (-self.params[2] + 1e-9)),
                str(self.params[1] / (-self.params[2] + 1e-9)),
                str(self.params[3] / (-self.params[2] + 1e-9)),
            ]
        )


@dataclass
class CurvedPlaneFit(Fit):
    """
    z = k(x+a)(y+b) + c
    """

    @staticmethod
    def _eval(x, y, a, b, c, k):
        return k * (x + a) * (y + b) + c


@dataclass
class WikiFit(Fit):
    """
    z = x * (1 + y/k)
    """

    @staticmethod
    def _eval(x, y, k):
        return x * (1 + y / k)


@dataclass
class WikiFit2(Fit):
    """
    x * (k2 * y + 1)             -- current
    (k1 * x + c1) * (k2 * y + 1) -- good, all low loss, semi-consistent constants
    k1 * (x + c1) * (y + 1)      -- bad, high loss
    k1 * (x + c1) * (k2 * y + 1) -- also good, but equivalent to (1), exposes some consistency in c1
    k3 * (k1 * x) * (k2 * y + 1) -- meh, ~10% loss but some consistentcy wrt to slot and stat

    hypothesis:
        scaling = f(base, ...) * g(level, ...)

        g(level, ...) is same as before
        still depends on stat_group

        f(base, ...) depends on
            slot location (head, body, gloves, etc)
                this is a constant multiplier
                    feet    1
                    hands   1.13555556
                    head    1.26
                    legs    1.38666
                    body    1.5133

            slot series (leather, cotton, plate, etc)
            stat (int, wis, str, etc)
                this controls the min and max values
                probably unique for each (slot_series, stat) pair
                maybe modeled as mult*base + offset

            stat group (pabs, edb, mits, etc)
                admin confirms this exists
                seems redundant if the (slot_series, stat) constants exist
                but ive confirmed that pabs on the same equip scale differently
                so both must exist

            so in summary...
                slot location       => body armor is always N-times better than shoes
                (slot_series, stat) => min / max values (?)
                stat_group          => scaling rate (?)

        scaling is confirmed to be slightly non-linear
    """

    params: list[float]
    denom: float
    loc_mult: float

    @staticmethod
    def _eval(
        x,
        y,
        denom,
        loc_mult,
        #
        # k,
        m,
        b,
        # k,
        # c,
        # k3,
    ):
        level_term = y / denom + 1
        # base_term = 1.22 ** (0.031 * x + b)
        base_term = 1.22 ** (x * m + b)
        return loc_mult * base_term * level_term

    def eval(self, x, y):
        return self._eval(x, y, self.denom, self.loc_mult, *self.params)

    @classmethod
    def from_points(cls, pts: list[Point3], denom: float, loc_mult: float):
        def eval(pts, *args):
            return cls._eval(pts[:, 0], pts[:, 1], denom, loc_mult, *args)

        arr = numpy.array(pts, dtype=numpy.float64)
        result: tuple = scipy.optimize.curve_fit(
            eval,
            arr[:, :2],
            arr[:, 2],
            (
                # random.choice([0, 10, 100])
                # for _ in range(len(signature(cls._eval).parameters) - 4)
                # 5.0 * random.random(),
                5.0 * random.random(),
                5.0 * random.random(),
            ),
            bounds=(-10, 100),
        )

        return cls(result[0], denom, loc_mult)


def pp(x: float | list[float] | tuple[float, ...], n=3):
    if isinstance(x, float):
        return f"{x:.{n}f}"
    elif isinstance(x, (list, tuple)):
        return ", ".join(pp(y) for y in x)
    else:
        raise Exception()


if __name__ == "__main__":
    asyncio.run(main())
