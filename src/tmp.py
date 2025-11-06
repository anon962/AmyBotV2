import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from inspect import signature
from typing import TypeAlias, TypeVar

import numpy
import scipy
import scipy.optimize
import torch

from classes.core.server.parse_equip_name import parse_equip_name
from classes.db import init_db
from config.paths import DATA_DIR

WORLD = "isekai"
# WORLD = "persistent"

# FIT_TYPE = "curved"
# FIT_TYPE = "plane"
# FIT_TYPE = "wiki"
FIT_TYPE = "wiki2"


async def main():
    edb = init_db()

    counts = tally(edb)

    tmp_dir = DATA_DIR / "tmp"
    tmp_dir.mkdir(exist_ok=True)

    for fp in tmp_dir.glob("*"):
        fp.unlink()

    items = list(counts.items())
    items.sort(key=lambda kv: len(kv[1]), reverse=True)

    min_result_count = 10 if WORLD == "isekai" else 60

    # plots
    missing_filters = set()
    for gid, group in items:
        if len(group) < min_result_count:
            continue

        suffix_filters = []
        match gid[0]:
            case "Physical Mitigation":
                suffix_filters = ["Protection"]
            case "Magical Mitigation":
                suffix_filters = ["Warding"]
            case "Block":
                suffix_filters = ["Shielding", "Barrier"]
            case "Parry":
                suffix_filters = ["Nimble"]
            case "Attack Crit Damage":
                suffix_filters = ["Balance"]
            case "Attack Accuracy":
                suffix_filters = ["Balance"]
            case "Magic Damage":
                suffix_filters = ["Radiant", "Destruction"]
            case "Magic Accuracy":
                suffix_filters = ["Focus"]
            case "Evade Chance":
                suffix_filters = ["Fleet"]
            case "Intelligence":
                suffix_filters = ["Owl"]
            case "Burden":
                suffix_filters = ["Mithril"]
            case "Wisdom":
                suffix_filters = []
            case "Agility":
                suffix_filters = []
            case "Interference":
                suffix_filters = ["Mithril"]
            case "Crushing":
                suffix_filters = ["Dampening", "Reinforced"]
            case "Piercing":
                suffix_filters = ["Deflection", "Reinforced"]
            case "Slashing":
                suffix_filters = ["Stoneskin", "Reinforced"]
            case _:
                missing_filters.add(gid[0])
                continue

        if gid[0] not in ["Block", "Parry"]:
            continue

        group = [
            x
            for x in group
            if all(x["name_parts"]["suffix"] != y for y in suffix_filters)
        ]
        if len(group) < min_result_count:
            continue

        name = "_".join(str(x) for x in gid)
        print(f"{len(group)}x", name)

        best: tuple = None  # type: ignore
        for _ in range(100):
            pts = [(x["base"], x["d"]["level"], x["value"]) for x in group]

            try:
                if FIT_TYPE == "curved":
                    fit = CurvedPlaneFit.from_points(pts)
                elif FIT_TYPE == "wiki":
                    fit = WikiFit.from_points(pts)
                elif FIT_TYPE == "wiki2":
                    fit = WikiFit2.from_points(pts)
                else:
                    fit = PlaneFit.from_points(pts)
            except Exception:
                print("\tFailed to fit")
                break

            loss = fit.calc_loss(pts)

            if not best or loss < best[0]:
                best = (loss, fit)

        if not best:
            continue

        loss, fit = best
        print("\tloss:", pp(loss))
        print("\tplane:", str(fit))

        plot(name, group, fit, loss)

    print(f"Missing filters for:", missing_filters)


def plot(name: str, group: list[dict], fit: "Fit", loss: float):
    import pandas
    import plotly.express as px
    import plotly.graph_objects as go

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

    min_base = min(v["base"] for v in group)
    max_base = max(v["base"] for v in group)
    x = numpy.arange(min_base * 0.9, max_base * 1.1, (max_base - min_base) / 100)

    min_level = min(v["d"]["level"] for v in group)
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


def tally(edb):
    if WORLD == "isekai":
        rs = edb.execute(
            """
            SELECT id, key, data
            FROM equips
            WHERE is_isekai = 1
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

        if not isinstance(d["level"], int):
            continue
        # if d["level"] >= 50:
        #     continue

        for cat_name, cat in d["stats"].items():
            for stat_name, stat in cat.items():
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
    for k, vs in items[-20:]:
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
            tuple(100 for _ in range(len(signature(cls._eval).parameters) - 2)),
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

        loss = (preds - zs).abs()
        loss = loss.mean() / zs.mean()
        loss = loss.item()
        return loss

    def __str__(self) -> str:
        return " ".join([pp(p, 4) for p in self.params])

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
    params: list[float]

    @staticmethod
    def _eval(x, y, c1, k2):
        return 0.0015 * (x + c1) * (k2 * y)


def pp(x: float | list[float] | tuple[float, ...], n=3):
    if isinstance(x, float):
        return f"{x:.{n}f}"
    elif isinstance(x, (list, tuple)):
        return ", ".join(pp(y) for y in x)
    else:
        raise Exception()


if __name__ == "__main__":
    asyncio.run(main())
