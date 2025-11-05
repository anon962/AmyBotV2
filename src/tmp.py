import itertools
import json
import sqlite3
from math import prod
from typing import Literal, TypeAlias

import torch
from attr import dataclass
from more_itertools import numeric_range
from tqdm import tqdm

from classes.core.server.parse_equip_name import parse_equip_name
from classes.db import init_db
from config.paths import DATA_DIR

db = init_db()


def main():
    counts = tally()

    tmp_dir = DATA_DIR / "tmp"
    tmp_dir.mkdir(exist_ok=True)

    items = counts.items()
    gid, group = max(items, key=lambda kv: len(kv[1]))
    print(gid, len(group))

    base = [v["base"] for v in group]
    level = [v["d"]["level"] for v in group]
    value = [v["value"] for v in group]

    db_file = DATA_DIR / "tmp" / "progress.sqlite"
    db_file.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(db_file)
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            id      TEXT        PRIMARY KEY
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS solutions (
            id          TEXT        NOT NULL,
            params      TEXT        NOT NULL,
            error       REAL        NOT NULL,
            PRIMARY KEY (id, params)
        )
        """
    )

    print(base)
    print(level)
    print(value)

    for c in iter_candidates(db):
        sols = eval_candidate(c, base, level, value)

        for s in sols:
            db.execute(
                """
                INSERT INTO solutions (
                    id, params, error
                ) VALUES (
                    ?, ?, ?
                )
                """,
                [
                    json.dumps(c.to_id()),
                    json.dumps(s["params"]),
                    s["error"],
                ],
            )

        db.commit()


def tally():
    rs = db.execute(
        """
        SELECT id, key, data
        FROM equips
        WHERE json_extract(data, '$.owner.source_name') IS NOT NULL
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

                name_parts = parse_equip_name(d["name"])

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


NUM_OPS = 3

MultOp: TypeAlias = Literal["mult"]  # cx
InvOp: TypeAlias = Literal["inv"]  # 1 / x
AddOp: TypeAlias = Literal["add"]  # x + c
ExpOp: TypeAlias = Literal["exp"]  # x^c
Exp2Op: TypeAlias = Literal["exp2"]  # c^x
LogOp: TypeAlias = Literal["log"]  # log(x)
Op: TypeAlias = MultOp | AddOp | ExpOp | Exp2Op | LogOp
OpBatch: TypeAlias = tuple[Op, Op, Op]


@dataclass
class Candidate:
    base_ops: OpBatch
    level_ops: OpBatch
    merge_op: AddOp | MultOp | ExpOp | Exp2Op
    merged_ops: OpBatch

    def __post_init__(self):
        for batch in [self.base_ops, self.level_ops, self.merged_ops]:
            seen = set()
            prev_was_none = False
            for op in batch:
                if op is None:
                    prev_was_none = True
                    continue
                elif prev_was_none:
                    raise Exception(f"Non-null value follows null value: {batch}")

                if op in seen:
                    raise Exception(f"Duplicate op: {op} {batch}")
                seen.add(op)

    def to_id(self) -> tuple:
        id = tuple([*self.base_ops, *self.level_ops, self.merge_op, *self.merged_ops])
        return id

    @classmethod
    def from_id(cls, id) -> "Candidate":
        return cls(
            base_ops=id[0 * NUM_OPS : 1 * NUM_OPS],
            level_ops=id[1 * NUM_OPS : 2 * NUM_OPS],
            merge_op=id[2 * NUM_OPS],
            merged_ops=id[2 * NUM_OPS + 1, 3 * NUM_OPS + 1],
        )

    def __hash__(self) -> int:
        return hash(self.to_id())

    def __eq__(self, value: object) -> bool:
        return isinstance(value, Candidate) and hash(self) == hash(value)

    def __str__(self) -> str:
        return "|".join(
            [
                "-".join(self.base_ops),
                "-".join(self.level_ops),
                self.merge_op,
                "-".join(self.merged_ops),
            ]
        )


ALL_OPS = [
    "mult",
    # "inv",
    "add",
    "exp",
    "exp2",
    "log",
]
MERGE_OPS = ["add", "mult", "exp", "exp2"]


def iter_candidates(db):
    is_done = lambda id: bool(
        db.execute("SELECT 1 FROM progress WHERE id = ?", [id]).fetchone()
    )
    insert = lambda id: bool(
        db.execute("INSERT INTO progress (id) VALUES (?)", [id]).fetchone()
    )

    pbar = tqdm()
    idx = 0
    for base_ops in itertools.permutations(ALL_OPS, NUM_OPS):
        for level_ops in itertools.permutations(ALL_OPS, NUM_OPS):
            for merge_op in MERGE_OPS:
                for merged_ops in itertools.permutations(ALL_OPS, NUM_OPS):
                    idx += 1
                    pbar.update()

                    candidate = Candidate(
                        base_ops=base_ops,  # type: ignore
                        level_ops=level_ops,  # type: ignore
                        merge_op=merge_op,  # type: ignore
                        merged_ops=merged_ops,  # type: ignore
                    )
                    if is_done(json.dumps(candidate.to_id())):
                        continue

                    yield candidate

                    insert(json.dumps(candidate.to_id()))
                    db.commit()


OP_RANGES = dict(
    mult=(
        list(
            itertools.chain(
                numeric_range(0, 1, 0.1),
                # numeric_range(1, 50, 3),
                # numeric_range(50, 200, 10),
                # numeric_range(-5, 0, 0.5),
            )
        )
    ),
    inv=([-99]),
    add=(
        list(
            itertools.chain(
                numeric_range(0, 5, 0.25),
                # numeric_range(5, 100, 5),
                # numeric_range(-100, 0, 5),
            )
        )
    ),
    exp=(
        list(
            itertools.chain(
                numeric_range(0, 5, 0.25),
                # numeric_range(5, 10, 0.5),
            )
        )
    ),
    exp2=(
        list(
            itertools.chain(
                numeric_range(0, 5, 0.25),
                # numeric_range(5, 100, 5),
            )
        )
    ),
    log=([-99]),
)


def eval_candidate(
    c: Candidate,
    base_raw: list[float],
    level_raw: list[float],
    values_raw: list[float],
    batch_size=1_000_000,
    thresh=0.01,
):
    assert len(base_raw) == len(level_raw) == len(values_raw)
    n = len(base_raw)

    base_src = torch.tensor(base_raw, dtype=torch.float).to("cuda")  # n
    level_src = torch.tensor(level_raw, dtype=torch.float).to("cuda")  # n
    values = torch.tensor(values_raw, dtype=torch.float).to("cuda")  # n

    o = NUM_OPS * 3  # number of constants

    print(c)
    sols = []

    prod_iter = itertools.product(
        *[
            OP_RANGES[op]
            for op in [
                *c.base_ops,
                *c.level_ops,
                *c.merged_ops,
            ]
        ]
    )

    total = prod(
        [
            len(OP_RANGES[op])
            for op in [
                *c.base_ops,
                *c.level_ops,
                *c.merged_ops,
            ]
        ]
    )
    pbar = tqdm(total=total)

    while True:
        params = list(itertools.islice(prod_iter, batch_size))
        pbar.update(len(params))

        b = len(params)
        if b == 0:
            break
        params = (
            torch.tensor(params, dtype=torch.float)
            .to("cuda")
            .unsqueeze(0)
            .expand(n, b, o)
        )  # [n b o]

        param_idx = 0

        # base
        x = base_src.unsqueeze(1).repeat(1, b)  # n b
        for op in c.base_ops:
            match op:
                case "add":
                    x = x + params[:, :, param_idx]
                case "mult":
                    x = x * params[:, :, param_idx]
                case "inv":
                    x = 1 / x
                case "exp":
                    x = x ** params[:, :, param_idx]
                case "exp2":
                    x = params[:, :, param_idx] ** x
                case "log":
                    x = torch.log(x)
                case _:
                    raise Exception()
            param_idx += 1
        base = x

        # level
        x = level_src.unsqueeze(1).repeat(1, b)  # n b
        for op in c.level_ops:
            match op:
                case "add":
                    x = x + params[:, :, param_idx]
                case "mult":
                    x = x * params[:, :, param_idx]
                case "inv":
                    x = 1 / x
                case "exp":
                    x = x ** params[:, :, param_idx]
                case "exp2":
                    x = params[:, :, param_idx] ** x
                case "log":
                    x = torch.log(x)
                case _:
                    raise Exception()
            param_idx += 1
        level = x

        # merge
        match c.merge_op:
            case "add":
                x = base + level
            case "mult":
                x = base * level
            case "exp":
                x = base**level
            case "exp2":
                x = level**base
            case _:
                raise Exception()

        # post-merge
        for op in c.merged_ops:
            match op:
                case "add":
                    x = x + params[:, :, param_idx]
                case "mult":
                    x = x * params[:, :, param_idx]
                case "inv":
                    x = 1 / (x + 1e-8)
                case "exp":
                    x = x ** params[:, :, param_idx]
                case "exp2":
                    x = params[:, :, param_idx] ** x
                case "log":
                    x = torch.log(x)
                case _:
                    raise Exception()
            param_idx += 1

        # error
        error = values.unsqueeze(1).expand(n, b)
        error = (error - x) ** 2
        error = error.mean(dim=0)

        for idx in range(b):
            if error[idx] < thresh:
                print(
                    "\t",
                    pp(x[0, idx].item()),
                    pp(error[idx].item()),
                    pp(base[0, idx].item()),
                    pp(level[0, idx].item()),
                    "|",
                    pp(params[0, idx, :].tolist()),
                )

                sols.append(
                    dict(
                        error=error[idx].item(),
                        params=params[0, idx, :].tolist(),
                    )
                )

    return sols


def pp(x: float | list[float]):
    if isinstance(x, float):
        return f"{x:.3f}"
    elif isinstance(x, list):
        return ", ".join(pp(y) for y in x)
    else:
        raise Exception()


if __name__ == "__main__":
    main()
