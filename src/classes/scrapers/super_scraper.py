import json
import re
import time
from dataclasses import dataclass
from datetime import datetime

import bs4
from bs4 import BeautifulSoup, Tag
from classes.db import DB
from config import logger, paths
from utils.http import do_get
from utils.json_cache import JsonCache
from utils.parse import parse_equip_link, price_to_int
from utils.rate_limit import rate_limit
from yarl import URL

logger = logger.bind(tags=["super"])

_limit = rate_limit(calls=1, period=5, scope="super")
do_get = _limit(do_get)


@dataclass
class _Cell:
    text: str
    href: str | None
    td: Tag


class SuperScraper:
    HOME_URL = URL("https://reasoningtheory.net")

    HTML_CACHE_FILE = JsonCache(paths.CACHE_DIR / "super_html.json", default=dict)
    html_cache: dict = HTML_CACHE_FILE.load()  # type: ignore

    @classmethod
    async def update(cls) -> None:
        async def main():
            """Fetch auctions that haven't been parsed yet"""
            with DB:
                rows = DB.execute(
                    """
                    SELECT id, is_complete FROM super_auctions
                    WHERE last_fetch_time = 0
                    OR is_complete = 0
                    OR is_complete is NULL
                    """
                ).fetchall()

            for r in rows:
                if r["is_complete"] is None:
                    await cls.scan_auction(r["id"], allow_cached=True)
                elif r["is_complete"] == 0:
                    await cls.scan_auction(r["id"], allow_cached=False)
                elif r["is_complete"] == 1:
                    # Retry auctions with fails
                    with DB:
                        fails = DB.execute(
                            """
                            SELECT * FROM super_fails
                            WHERE id_auction = ?
                            """,
                            (r["id"],),
                        ).fetchall()

                        if len(fails) > 0:
                            purge_auction(r["id"], equips=True, mats=True, fails=True)
                            await cls.scan_auction(r["id"], allow_cached=True)

        def purge_auction(
            id: str, listing=False, equips=False, mats=False, fails=False
        ) -> None:
            # fmt: off
            with DB:
                if fails: DB.execute("DELETE FROM super_fails WHERE id_auction = ?",(id,),)
                if equips: DB.execute("DELETE FROM super_equips WHERE id_auction = ?",(id,),)
                if mats: DB.execute("DELETE FROM super_mats WHERE id_auction = ?",(id,),)
                if listing: DB.execute("DELETE FROM super_auctions WHERE id = ?",(id,),)
            # fmt: on

        return await main()

    @classmethod
    async def refresh_list(cls) -> list[dict]:
        """Fetch list of Super's auctions and update DB

        This only handles the list on the homepage (https://reasoningtheory.net),
        not the equip / item data
        """

        async def main():
            page: str = await do_get(cls.HOME_URL, content_type="text")
            # from test.stubs.super import homepage; page = homepage  # fmt: skip
            soup = BeautifulSoup(page, "lxml")

            row_els = soup.select("tbody > tr")
            row_data: list[dict] = []
            for el in row_els:
                data = parse_row(el)
                insert_db_row(data)
                row_data.append(data)

            return row_data

        def parse_row(tr: bs4.Tag) -> dict:
            # Check pre-conditions
            cells = [cls._td_to_dict(td) for td in tr.select("td")]
            [idxCell, dateCell, _, _, _, threadCell] = cells
            assert threadCell.href

            # Parse
            title = idxCell.text
            end_time = datetime.strptime(
                dateCell.text + "+0000", r"%m-%d-%Y%z"
            ).timestamp()
            id = re.search(r"showtopic=(\d+)", threadCell.href).group(1)  # type: ignore

            # Return
            data = dict(id=id, title=title, end_time=end_time)
            return data

        def insert_db_row(data: dict) -> None:
            with DB:
                DB.execute(
                    """
                    INSERT OR IGNORE INTO super_auctions
                    (id, title, end_time, is_complete, last_fetch_time) VALUES (:id, :title, :end_time, NULL, 0)
                    """,
                    data,
                )

        return await main()

    @classmethod
    async def scan_auction(cls, auction_id: str, allow_cached=True) -> None:
        """Fetch itemlist for auction

        Args:
            auction_id:

        Raises:
            Exception:
        """

        PATTS = {
            "price_buyer": re.compile(
                # 1803k (sickentide #66.5)
                r"^(\d+[mkc]) \((.*) #[\d.]+\)$"
            ),
            "quant_name": re.compile(
                # 30 Binding of Slaughter
                r"^(\d+) (.*)$"
            ),
            "level_stats": re.compile(
                # 455, MDB 36%, Holy EDB 73%
                r"^(\d+|Unassigned|n/a)(?:, (.*))?$"
            ),
        }

        async def main():
            page = await fetch(auction_id, allow_cached=allow_cached)
            trs = page.select("tbody > tr")
            rows: list[list[_Cell]] = []
            for tr in trs:
                cells = cls.item_row_to_cells(tr)
                rows.append(cells)

            # Parse auction data
            item_data = []
            for cells in rows:
                try:
                    data = parse_quirky_row(auction_id, cells) or parse_row(cells)
                    data["id_auction"] = auction_id
                    item_data.append(data)
                except:
                    logger.exception(f"Failed to parse {cells}")
                    with DB:
                        item_code = cells[0].text
                        item_name = cells[1].text
                        tr = trs[rows.index(cells)]
                        DB.execute(
                            """
                            INSERT OR REPLACE INTO super_fails
                            (id, id_auction, summary, html) VALUES (?, ?, ?, ?)
                            """,
                            (item_code, auction_id, item_name, str(tr)),
                        )

            # Update item data in db
            with DB:
                for item in item_data:
                    if item["_type"] == "equip":
                        DB.execute(
                            """
                            INSERT OR REPLACE INTO super_equips 
                            (id, id_auction, name, eid, key, is_isekai, level, stats, price, bid_link, next_bid, buyer, seller)
                            VALUES (:id, :id_auction, :name, :eid, :key, :is_isekai, :level, :stats, :price, :bid_link, :next_bid, :buyer, :seller)
                            """,
                            item,
                        )
                    else:
                        DB.execute(
                            """
                            INSERT OR REPLACE INTO super_mats 
                            (id, id_auction, name, quantity, unit_price, price, bid_link, next_bid, buyer, seller)
                            VALUES (:id, :id_auction, :name, :quantity, :unit_price, :price, :bid_link, :next_bid, :buyer, :seller)
                            """,
                            item,
                        )

            # Update auction status in db
            with DB:
                is_complete = "Auction ended" in page.select_one("#timing").text  # type: ignore
                is_complete = int(is_complete)
                with DB:
                    DB.execute(
                        """
                        UPDATE super_auctions
                        SET is_complete = ?
                        WHERE id = ?
                        """,
                        (is_complete, auction_id),
                    )

        async def fetch(id: str, allow_cached=False) -> BeautifulSoup:
            path = f"itemlist{id}"

            if not allow_cached or path not in cls.html_cache:
                # Fetch auction page
                html: str = await do_get(cls.HOME_URL / path, content_type="text")
                cls.html_cache[path] = html
                cls.HTML_CACHE_FILE.dump(cls.html_cache)

                # Update db
                with DB:
                    DB.execute(
                        """
                        UPDATE super_auctions SET
                            last_fetch_time = ?
                        """,
                        (time.time(),),
                    )

            html = cls.html_cache[path]
            page = BeautifulSoup(html, "lxml")
            return page

        def parse_quirky_row(auction_id: str, cells: list[_Cell]) -> dict | None:
            [codeCell, nameCell, infoCell, _, nextBidCell, *_] = cells

            if auction_id == "194262" and codeCell.text == "Mat00":
                # Pony figurine set -> 1 Pony figurine set
                nameCell.text = "1 " + nameCell.text
                return parse_mat_row(cells)
            if auction_id == "194041" and "Bid" in nextBidCell.text:
                nextBidCell.text = nextBidCell.td.text.replace("Bid", "")
            if infoCell.text.startswith("seller: "):
                logger.info(
                    f'Discarding info "{infoCell.text}" for "{nameCell.text}" in auction {auction_id}'
                )
                infoCell.text = ""
                return parse_row(cells)

            return None

        def parse_row(cells: list[_Cell]) -> dict:
            [codeCell, *_] = cells
            if codeCell.text.startswith("Mat"):
                return parse_mat_row(cells)
            else:
                return parse_equip_row(cells)

        def parse_mat_row(row_els: list[_Cell]) -> dict:
            [codeCell, nameCell, _, currentBidCell, nextBidCell, sellerCell] = row_els

            id = codeCell.text
            seller = sellerCell.text

            [quantity, name] = PATTS["quant_name"].search(nameCell.text).groups()  # type: ignore
            quantity = int(quantity)

            [buyer, bid_link, price] = parse_price_buyer(currentBidCell)
            unit_price = price / quantity if price else None

            next_bid = price_to_int(nextBidCell.text)

            data = dict(
                _type="mat",
                id=id,
                name=name,
                quantity=quantity,
                unit_price=unit_price,
                price=price,
                bid_link=bid_link,
                next_bid=next_bid,
                buyer=buyer,
                seller=seller,
            )
            return data

        def parse_equip_row(cells: list[_Cell]) -> dict:
            [
                codeCell,
                nameCell,
                infoCell,
                currentBidCell,
                nextBidCell,
                sellerCell,
            ] = cells

            id = codeCell.text
            name = nameCell.text
            seller = sellerCell.text
            [eid, key, is_isekai] = parse_equip_link(nameCell.href)  # type: ignore
            [buyer, bid_link, price] = parse_price_buyer(currentBidCell)
            next_bid = price_to_int(nextBidCell.text)

            if infoCell.text == "":
                # Super didn't provide any info
                level = None
                stats = "{}"
            else:
                # Verify we're parsing smth like "500, ADB 94%, EDB 55%, ..."
                assert re.search(PATTS["level_stats"], infoCell.text)

                [level_text, *stats] = infoCell.text.split(",")
                if level_text == "Unassigned":
                    level = 0
                elif level_text == "n/a":
                    level = None
                else:
                    level = int(level_text)
                    if int(level) != float(level):
                        raise Exception

                stats = [x.strip() for x in stats]
                stats = json.dumps(stats)

            data = dict(
                _type="equip",
                id=id,
                name=name,
                eid=eid,
                key=key,
                is_isekai=is_isekai,
                level=level,
                stats=stats,
                price=price,
                bid_link=bid_link,
                next_bid=next_bid,
                buyer=buyer,
                seller=seller,
            )
            return data

        def parse_price_buyer(
            cell: _Cell,
        ) -> tuple[str, str | None, int] | tuple[None, None, None]:
            m = PATTS["price_buyer"].search(cell.text)
            if m:
                # Item was sold
                [price, buyer] = m.groups()
                price = price_to_int(price)
                return (buyer, cell.href, price)
            else:
                # Item was unsold
                if cell.text != "0":
                    raise Exception
                return (None, None, None)

        return await main()

    @classmethod
    def _td_to_dict(cls, td: Tag) -> _Cell:
        a = td.select_one("a")
        result = _Cell(text=td.text, href=str(a["href"]) if a else None, td=td)
        return result

    @classmethod
    def item_row_to_cells(cls, tr: Tag) -> list[_Cell]:
        tds = tr.select("td")
        assert len(tds) == 6

        cells = [cls._td_to_dict(td) for td in tr.select("td")]
        cells[4].text = tds[4].select_one("div:not(.customButton)").text  # type: ignore

        return cells


if __name__ == "__main__":
    # fmt: off
    import asyncio
    async def main():
        await SuperScraper.refresh_list()
        await SuperScraper.update()
    asyncio.run(main())
