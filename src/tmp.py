import json

from classes.core.server.parse_equip_name import parse_equip_name
from classes.db import init_db

db = init_db()

"""
tier         base values
              min   max
crude           0    30
fair           30    60
average        60    90
superior       90   130
magnificent   130   170
legendary     170   200
"""


def main():
    counts = tally()

    # cs = counts[
    #     (
    #         "Average",
    #         "Plate Helmet",
    #         "Magical Mitigation",
    #     )
    # ]
    # Path(DATA_DIR / "tmp").write_text(
    #     ",".join(str(x) for x in (sorted([c["base"] for c in cs]))),
    # )

    items = counts.items()
    items = sorted(items, key=lambda kv: len(kv[1]), reverse=True)
    items = [(k, cs) for k, cs in items if len(cs) >= 3]

    kpads = [
        max(len(k[idx] or "") for k, cs in items) for idx in range(len(items[0][0]))
    ]
    for k, cs in items:
        vs = sorted([v["base"] for v in cs], key=lambda v: v)
        vs = list(vs)
        pad = lambda s, n: f"{s or '':<{n}}"
        print(
            f"{len(vs):<5}",
            f"{vs[0]:<6.1f}",
            f"{vs[-1]:<6.1f}",
            # f"{k[-1][:29]:<30}",
            # cs[0]["name"],
            *[pad(pt, kpads[idx] + 3) for idx, pt in enumerate(k)],
        )


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

    bad = set()

    # for d in data:
    #     try:
    #         parse_equip_name(d["name"])
    #     except:
    #         bad.add(d["name"])

    # bad = sorted(list(bad), key=lambda x: x)
    # for b in bad:
    #     print(b)

    tally = dict()
    for d in data:
        # if "Plate Greaves" in d["name"]:
        #     print(
        #         f"https://hentaiverse.org/isekai/equip/{d['id']}/{d['key']}",
        #         d["name"],
        #     )

        for cat_name, cat in d["stats"].items():
            for stat_name, stat in cat.items():
                # if stat_name != "Crushing":
                #     continue
                if stat["base"] == 0:
                    continue
                # bad.add((d["id"], d["key"]))
                # if any(
                #     x in d["name"] for x in ["Magnificent", "Legendary", "Peerless"]
                # ):
                #     continue

                name_parts = parse_equip_name(d["name"])

                key = (
                    # stat_name,
                    name_parts["tier"],
                    # name_parts["prefix"],
                    # name_parts["type"],
                    # name_parts["suffix"],
                )
                tally.setdefault(key, [])
                tally[key].append(
                    dict(
                        stat_name=stat_name,
                        tier=name_parts["tier"],
                        name=d["name"],
                        base=stat["base"] or stat["value"],
                    )
                )

    # for id, key in bad:
    #     print(f"https://hentaiverse.org/isekai/equip/{id}/{key}")
    #     print(id, key)
    #     resp = requests.get(
    #         f"https://hvdata.gisadan.dev/equip?key={key}&eid={id}&is_isekai=true"
    #     )

    #     match resp.status_code:
    #         case 200:
    #             pass
    #         case 404:
    #             pass
    #         case _:
    #             raise Exception()

    # for eid, key in bad:
    #     html_query = db.execute(
    #         "SELECT html,created_at FROM equips_html WHERE id=? AND key = ?", [eid, key]
    #     ).fetchone()

    #     from classes.core.server import equip_parser_beta

    #     data = equip_parser_beta.parse_equip_html(html_query["html"])

    #     print(data)

    #     db.execute(
    #         """
    #         INSERT OR REPLACE INTO equips (
    #             id, key, is_isekai, updated_at, data
    #         ) VALUES (
    #             ?, ?, ?, ?, ?
    #         )
    #         """,
    #         [eid, key, 1, html_query["created_at"], json.dumps(data)],
    #     )
    #     db.commit()

    items = list(tally.items())
    items.sort(key=lambda kv: len(kv[1]))
    # print("\n".join([f"{len(v)} {k}" for k, v in items]))

    return tally


main()
