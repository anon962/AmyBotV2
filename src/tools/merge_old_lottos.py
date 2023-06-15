import json
from classes.db import DB


old_data = "/home/anne/Downloads/lotto_data.json"
old_data = json.load(open(old_data, encoding="utf-8"))

with DB:
    for type in ["weapon", "armor"]:
        table = "lottery_weapon" if type == "weapon" else "lottery_armor"
        old_key = "w" if type == "weapon" else "a"

        missing = DB.execute(
            f'SELECT id FROM {table} WHERE "1_prize" IS NULL'
        ).fetchall()
        missing = [r["id"] for r in missing]

        for id in missing:
            grand_prize = old_data[old_key][str(id)]["eq"]
            if grand_prize != "No longer available":
                print("fixing", table, id)
                DB.execute(
                    f'UPDATE {table} SET "1_prize" = ? WHERE id = ?', (grand_prize, id)
                )
