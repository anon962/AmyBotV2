import asyncio
import datetime
import json
import sqlite3
from sqlite3 import Connection
from typing import Optional

import aiohttp
import requests
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from classes.core.server import logger
from classes.core.server.fetch_equip import LOGGER, fetch_equip_html, parse_equip_html
from classes.core.server.infer_equip_stats import infer_equip_stats
from classes.core.server.middleware import (
    ErrorLog,
    GZipWrapper,
    PerformanceLog,
    RequestLog,
)
from classes.db import init_db, insert_metadata, select_metadata
from config.paths import RANGES_FILE
from utils.html import select_one_or_raise
from utils.sql import WhereBuilder

HV_FETCH_DELAY_SECONDS = 3
RANGE_FETCH_DELAY_SECONDS = 86400 * 3

server = FastAPI()

# Enable CORS
server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints with a gzip'd response
GZipWrapper.endpoints = ["/export/sqlite", "/export/json"]

# Order matters, topmost are called first
server.add_middleware(ErrorLog)
server.add_middleware(GZipWrapper)
server.add_middleware(PerformanceLog)
server.add_middleware(RequestLog)

EXPORTED_TABLES = ['super_auctions', 'super_equips', 'super_mats', 'super_fails', 'kedama_auctions' ,'kedama_equips', 'kedama_mats', 'kedama_fails_item', 'lottery_weapon', 'lottery_armor']  # fmt: skip


@server.get("/super/search_equips")
def get_super_equips(
    name: Optional[str] = None,
    min_date: Optional[float] = None,
    max_date: Optional[float] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    seller: Optional[str] = None,
    seller_partial: Optional[str] = None,
    buyer: Optional[str] = None,
    buyer_partial: Optional[str] = None,
    complete: Optional[bool] = None,
    db: Connection = Depends(init_db),
):
    """Search for items sold at a Super auction

    The equip name and user name can be a comma separated list (eg "peerl,oak,heimd" instead of "Peerless Oak Staff of Heimdall")
    """

    where_builder = WhereBuilder("AND")

    # Create name filters
    #   eg "name=peer,waki" should match "Peerless * Wakizashi of the *"
    if name is not None:
        fragments = [x.strip() for x in name.split(",")]
        for fragment in fragments:
            where_builder.add("name LIKE ?", f"%{fragment}%")

    # Create date filters (utc)
    #   eg "min_date=1546300800" should match items sold on / after Jan 1, 2019
    if min_date is not None and max_date is not None and max_date < min_date:
        raise HTTPException(
            400, detail=f"min_date > max_date ({min_date} > {max_date})"
        )
    if min_date is not None:
        where_builder.add("sa.end_time >= ?", min_date)
    if max_date is not None:
        where_builder.add("sa.end_time <= ?", max_date)

    # Create price filters
    #   eg "max_price=1000" should match items sold for <=1000c
    if min_price is not None and max_price is not None and max_price < min_price:
        raise HTTPException(
            400, detail=f"min_price > max_price ({min_price} > {max_price})"
        )
    if min_price is not None:
        where_builder.add("se.price >= ?", min_price)
    if max_price is not None:
        wb = WhereBuilder("OR")
        wb.add("se.price <= ?", max_price)
        wb.add("se.price IS NULL", None)
        where_builder.add_builder(wb)

    # Create buyer filters
    if buyer is not None:
        # Exact match
        where_builder.add("buyer = ?", buyer)
    elif buyer_partial is not None:
        # Partial match
        fragments = [x.strip() for x in buyer_partial.split(",")]
        for fragment in fragments:
            where_builder.add("buyer LIKE ?", f"%{fragment}%")

    # Create seller filters
    if seller is not None:
        # Exact match
        where_builder.add("seller = ?", seller)
    elif seller_partial is not None:
        # Partial match
        fragments = [x.strip() for x in seller_partial.split(",")]
        for fragment in fragments:
            where_builder.add("seller LIKE ?", f"%{fragment}%")

    # Create completion filter
    if complete is not None:
        where_builder.add("sa_is_complete = ?", int(complete))

    # Query DB
    with db:
        where, data = where_builder.print()
        query = f"""
            SELECT se.*, sa.end_time as sa_end_time, sa.is_complete as sa_is_complete, sa.title as sa_title, sa.id as sa_id
            FROM super_equips as se INNER JOIN super_auctions as sa
            ON sa.id = se.id_auction
            {where}
            """
        logger.trace(f"Search super equips {query} {data}")
        rows = db.execute(query, data).fetchall()

    # Massage data structure
    result = [dict(row) for row in rows]
    for r in result:
        # Move joined cols into dict
        r["auction"] = dict(
            id=r["sa_id"],
            end_time=r["sa_end_time"],
            is_complete=r["sa_is_complete"],
            title=r["sa_title"],
        )
        for k in list(r.keys()):
            if k.startswith("sa_"):
                del r[k]

        # Stats col contains json
        r["stats"] = json.loads(r["stats"])

    # Return
    return result


@server.get("/kedama/search_equips")
def get_kedama_equips(
    name: Optional[str] = None,
    min_date: Optional[float] = None,
    max_date: Optional[float] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    seller: Optional[str] = None,
    seller_partial: Optional[str] = None,
    buyer: Optional[str] = None,
    buyer_partial: Optional[str] = None,
    db: Connection = Depends(init_db),
):
    """Search for items sold at a Kedama auction

    The equip name and user name can be a comma separated list (eg "peerl,oak,heimd" instead of "Peerless Oak Staff of Heimdall")
    """

    where_builder = WhereBuilder("AND")

    # Create name filters
    #   eg "name=peer,waki" should match "Peerless * Wakizashi of the *"
    if name is not None:
        fragments = [x.strip() for x in name.split(",")]
        for fragment in fragments:
            where_builder.add("name LIKE ?", f"%{fragment}%")

    # Create date filters (utc)
    #   eg "min_date=1546300800" should match items sold on / after Jan 1, 2019
    if min_date is not None and max_date is not None and max_date < min_date:
        raise HTTPException(
            400, detail=f"min_date > max_date ({min_date} > {max_date})"
        )
    if min_date is not None:
        where_builder.add("list.start_time >= ?", min_date)
    if max_date is not None:
        where_builder.add("list.start_time <= ?", max_date)

    # Create price filters
    #   eg "max_price=1000" should match items sold for <=1000c
    if min_price is not None and max_price is not None and max_price < min_price:
        raise HTTPException(
            400, detail=f"min_price > max_price ({min_price} > {max_price})"
        )
    if min_price is not None:
        where_builder.add("equip.price >= ?", min_price)
    if max_price is not None:
        wb = WhereBuilder("OR")
        wb.add("equip.price <= ?", max_price)
        wb.add("equip.price IS NULL", None)
        where_builder.add_builder(wb)

    # Create buyer filters
    if buyer is not None:
        # Exact match
        where_builder.add("buyer = ?", buyer)
    elif buyer_partial is not None:
        # Partial match
        fragments = [x.strip() for x in buyer_partial.split(",")]
        for fragment in fragments:
            where_builder.add("buyer LIKE ?", f"%{fragment}%")

    # Create seller filters
    if seller is not None:
        # Exact match
        where_builder.add("seller = ?", seller)
    elif seller_partial is not None:
        # Partial match
        fragments = [x.strip() for x in seller_partial.split(",")]
        for fragment in fragments:
            where_builder.add("seller LIKE ?", f"%{fragment}%")

    # Query DB
    with db:
        where, data = where_builder.print()
        query = f"""
            SELECT 
                equip.*,
                list.start_time as list_start_time,
                list.title as list_title,
                list.title_short as list_title_short,
                list.id as list_id
            FROM kedama_equips as equip INNER JOIN kedama_auctions as list
            ON list.id = equip.id_auction
            {where}
            """
        logger.trace(f"Search kedama equips {query} {data}")
        rows = db.execute(query, data).fetchall()

    # Massage data structure
    result = [dict(row) for row in rows]
    for r in result:
        # Move joined cols into dict
        r["auction"] = dict()
        for k in list(r.keys()):
            if k.startswith("list_"):
                r["auction"][k.replace("list_", "")] = r[k]
                del r[k]

        # Stats col contains json
        r["stats"] = json.loads(r["stats"])

    # Return
    return result


@server.get("/lottery/search")
def get_lottery(
    equip: Optional[str] = None,
    user: Optional[str] = None,
    user_partial: Optional[str] = None,
    min_date: Optional[float] = None,
    max_date: Optional[float] = None,
    db: Connection = Depends(init_db),
):
    """Search lottery data

    The equip name and user name can be a comma separated list (eg "peerl,oak,heimd" instead of "Peerless Oak Staff of Heimdall")
    """
    where_builder = WhereBuilder("AND")

    # Filter by item name
    if equip is not None:
        fragments = [x.strip() for x in equip.split(",")]
        for fragment in fragments:
            where_builder.add('"1_prize" LIKE ?', f"%{fragment}%")

    # Create date filters (utc)
    if min_date is not None and max_date is not None and max_date < min_date:
        raise HTTPException(
            400, detail=f"min_date > max_date ({min_date} > {max_date})"
        )
    if min_date is not None:
        where_builder.add("date >= ?", min_date)
    if max_date is not None:
        where_builder.add("date <= ?", max_date)

    # Filter by winner name
    user_cols = ["1_user", "1b_user", "2_user", "3_user", "4_user", "5_user"]
    if user is not None:
        wb = WhereBuilder("OR")
        for col in user_cols:
            wb.add(f'"{col}" = ?', user)
        where_builder.add_builder(wb)
    elif user_partial is not None:
        wb = WhereBuilder("OR")
        for col in user_cols:
            wb2 = WhereBuilder("AND")
            fragments = [x.strip() for x in user_partial.split(",")]
            for fragment in fragments:
                wb2.add(f'"{col}" LIKE ?', f"%{fragment}%")
            wb.add_builder(wb2)
        where_builder.add_builder(wb)

    # Run query
    rows = []
    with db:
        for type in ["weapon", "armor"]:
            where, query_data = where_builder.print()
            query = f"""
                SELECT * FROM lottery_{type}
                {where}
                """
            logger.trace(f"Search lottery {query} {query_data}")
            rs = db.execute(query, query_data).fetchall()
            for r in rs:
                data = dict(r)
                data["type"] = type
                rows.append(data)

    # Recombine columns into list of (item, winner)
    parse = json.loads

    result = []
    for r in rows:
        result.append(
            dict(
                date=r["date"],
                tickets=r["tickets"],
                lottery=dict(id=r["id"], type=r["type"]),
                prizes=[
                    [r["1_prize"], r["1_user"]],
                    [r["1b_prize"], r["1b_user"]],
                    [parse(r["2_prize"]), r["2_user"]],
                    [parse(r["3_prize"]), r["3_user"]],
                    [parse(r["4_prize"]), r["4_user"]],
                    [parse(r["5_prize"]), r["5_user"]],
                ],
            ),
        )

    return result


@server.get("/export/sqlite", response_class=PlainTextResponse)
def export_sqlite(db: Connection = Depends(init_db)):
    """Equivalent to .dump in sqlite3"""

    db_copy = sqlite3.connect(":memory:")
    db.backup(db_copy)

    with db_copy:
        # Delete unnecessary tables
        tables = db_copy.execute(
            'SELECT name FROM sqlite_master WHERE type = "table"'
        ).fetchall()
        tables = [x[0] for x in tables]

        for tbl in tables:
            if tbl not in EXPORTED_TABLES:
                db_copy.execute(f"DROP TABLE {tbl}")

    # Export
    resp = "\n".join(db_copy.iterdump())
    return resp


@server.get("/export/json")
def export_json(db: Connection = Depends(init_db)):
    """Dump DB as JSON"""
    resp = dict()

    with db:
        for tbl in EXPORTED_TABLES:
            resp[tbl] = [dict(x) for x in db.execute(f"SELECT * FROM {tbl}").fetchall()]

    return resp


@server.get("/equip")
async def get_equip(
    eid: int,
    key: str,
    is_isekai: bool = False,
):
    db = init_db()

    last_fetch = select_metadata(db, "last_hv_fetch")
    now = datetime.datetime.now()

    if last_fetch:
        last_fetch = datetime.datetime.fromisoformat(last_fetch)
        next_fetch = last_fetch + datetime.timedelta(seconds=HV_FETCH_DELAY_SECONDS)

        if now < next_fetch:
            insert_metadata(db, "last_hv_fetch", next_fetch.isoformat())

            delay = (next_fetch - now).seconds
            await asyncio.sleep(delay)
        else:
            insert_metadata(db, "last_hv_fetch", now.isoformat())
    else:
        insert_metadata(db, "last_hv_fetch", now.isoformat())

    db.commit()

    resp = fetch_equip_html(eid, key, is_isekai)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code)

    db.execute(
        """
        INSERT INTO equips_html (
            id, key, created_at, html
        ) VALUES (
            ?, ?, ?, ?
        )
        """,
        [eid, key, now.isoformat(), resp.text],
    )
    db.commit()

    if resp.text in ["Nope", "No such item"]:
        raise HTTPException(404)

    data = parse_equip_html(resp.text)
    data["calculations"] = infer_equip_stats(data)

    db.execute(
        """
        INSERT OR REPLACE INTO equips (
            id, key, updated_at, data
        ) VALUES (
            ?, ?, ?, ?
        )
        """,
        [eid, key, now.isoformat(), json.dumps(data)],
    )
    db.commit()

    return data


def create_range_update_task():
    async def poll_ranges():
        while True:
            db = init_db()

            delay = 0
            last_fetch = select_metadata(db, "last_range_update")

            if last_fetch:
                last_fetch = datetime.datetime.fromisoformat(last_fetch)
                next_fetch = last_fetch + datetime.timedelta(
                    seconds=RANGE_FETCH_DELAY_SECONDS
                )
                now = datetime.datetime.now()

                if now < next_fetch:
                    delay = (next_fetch - now).seconds
                    LOGGER.info(f"Sleeping for {delay}s before range fetch...")
                    await asyncio.sleep(delay)

            now = datetime.datetime.now()
            insert_metadata(db, "last_range_update", now.isoformat())
            db.commit()

            LOGGER.info("Fetching ranges...")
            async with aiohttp.ClientSession() as session:
                resp = await session.get("https://reasoningtheory.net/viewranges")
                html = await resp.text()

            if resp.status != 200:
                LOGGER.error(f"Range update failed with {resp.status}")

            soup = BeautifulSoup(html, "lxml")
            script_el = select_one_or_raise(soup, "[data-itemranges]")

            data = json.loads(script_el["data-itemranges"])  # type: ignore
            RANGES_FILE.write_text(json.dumps(data))
            LOGGER.info("Range update complete")

    return poll_ranges()
