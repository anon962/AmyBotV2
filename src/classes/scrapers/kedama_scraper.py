import copy
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional, Type

from aiohttp import ClientSession
from bs4 import BeautifulSoup, Tag
from classes.db import DB
from config import logger, paths
from utils.http import create_session, do_get, do_post
from utils.json_cache import JsonCache
from utils.misc import load_toml, split_lst
from utils.parse import parse_equip_link, parse_post_date, price_to_int
from utils.rate_limit import rate_limit
from yarl import URL

logger = logger.bind(tags=["kedama"])

_limit = rate_limit(calls=1, period=5, scope="forums")
do_get = _limit(do_get)
do_post = _limit(do_post)


@dataclass
class _Post:
    author: str
    author_id: int
    time: float
    post_id: int
    post_index: int
    content: list[list["_StrWithHref"]]
    el: Tag  # the entire post
    content_el: Tag  # just the post content


class KedamaScraper:
    # number of results EH displays per page in the search
    SEARCH_PAGE_SIZE = 25

    # username on forum
    KEDAMA_IGN = "SakiRaFubuKi"

    # forum id (/index.php?showuser=...)
    KEDAMA_ID = 1620623

    HTML_CACHE_FILE = JsonCache(paths.CACHE_DIR / "kedama_html.json", default=dict)
    html_cache: dict = HTML_CACHE_FILE.load()  # type: ignore

    @classmethod
    async def update(cls) -> None:
        auction_urls = await cls._fetch_auction_urls()
        for url in auction_urls:
            await cls.scan_auction(url)

    @classmethod
    async def scan_auction(cls, url: URL, allow_cached=True) -> None:
        """Fetch / parse thread then update DB"""

        async def main():
            page = await fetch(url)
            posts = extract_posts(page)

            # Extract listing data
            auction_id = url.query["showtopic"]
            title = page.select_one(".maintitle td").text.strip()  # type: ignore
            if m := re.search(r"(\d+\.?\d*)", title):
                title_short = m.group(1)
            else:
                title_short = "???"
            listing = dict(
                id=auction_id,
                title=title,
                title_short=title_short,
                start_time=posts[0].time,
                is_complete=True,
            )

            # Extract item data
            data = cls._parse_thread(auction_id, posts)

            # Remove old data
            purge(auction_id, listing=True, fails=True, mats=True, equips=True)

            # Insert new data
            with DB:
                DB.execute(
                    """
                    INSERT INTO kedama_auctions
                    (id, title_short, title, start_time, is_complete)
                    VALUES (:id, :title_short, :title, :start_time, :is_complete)
                    """,
                    listing,
                )

                DB.executemany(
                    """
                    INSERT INTO kedama_mats
                    (id, id_auction, name, quantity, unit_price, price, start_bid, post_index, buyer, seller)
                    VALUES (:id, :id_auction, :name, :quantity, :unit_price, :price, :start_bid, :post_index, :buyer, :seller)
                    """,
                    data["mats"],
                )

                DB.executemany(
                    """
                    INSERT INTO kedama_equips
                    (id, id_auction, name, eid, key, is_isekai, level, stats, price, start_bid, post_index, buyer, seller)
                    VALUES (:id, :id_auction, :name, :eid, :key, :is_isekai, :level, :stats, :price, :start_bid, :post_index, :buyer, :seller)
                    """,
                    data["equips"],
                )

                DB.executemany(
                    """
                    INSERT INTO kedama_fails_item
                    (id, id_auction, summary)
                    VALUES (:id, :id_auction, :summary)
                    """,
                    data["fails"],
                )

        async def fetch(url: URL) -> BeautifulSoup:
            """Fetch auction thread"""
            key = str(url)

            if not allow_cached or key not in cls.html_cache:
                # Fetch
                html: str = await do_get(url, content_type="text")
                cls.html_cache[key] = html
                cls.HTML_CACHE_FILE.dump(cls.html_cache)

                # Update db
                with DB:
                    DB.execute(
                        "UPDATE kedama_auctions SET last_fetch_time = ?", (time.time(),)
                    )

            html = cls.html_cache[key]
            page = BeautifulSoup(html, "lxml")
            return page

        def extract_posts(page: BeautifulSoup) -> list[_Post]:
            """Get posts on forum page"""

            post_els = page.select(
                "*:not(#topicoptionsjs) > div.borderwrap > table:first-child"
            )
            assert 1 <= len(post_els) <= 20

            posts: list[_Post] = []
            for post_el in post_els:
                trs = post_el.select(":scope > tr")
                assert len(trs) == 3

                [top_el, mid_el, _] = trs

                # Parse top section of post
                date_el = top_el.select_one("td.subtitle > div:first-child > span")
                time = parse_post_date(date_el.text)  # type: ignore

                index_el = top_el.select_one(".postdetails > a[onclick]")
                post_index = re.fullmatch(r"#(\d+)", index_el.text).group(1)  # type: ignore
                post_index = int(post_index)
                post_id = re.search(r"link_to_post\((\d+)\)", index_el["onclick"]).group(1)  # type: ignore
                post_id = int(post_id)

                # Parse middle section of post
                tds = mid_el.select(":scope > td")
                assert tds and len(tds) == 2

                username_el = tds[0].select_one(".postdetails > .bigusername > a")
                author = username_el.text  # type: ignore
                profile_url = URL(str(username_el["href"]))  # type: ignore
                author_id = int(profile_url.query["showuser"])

                content_el = tds[1].select_one(
                    ":scope > .postcolor"
                )  # cuts off signature section
                content = [x for x in _PostParser.parse(content_el) if x]  # type: ignore

                posts.append(
                    _Post(
                        author=author,
                        author_id=author_id,
                        time=time,
                        post_id=post_id,
                        post_index=post_index,
                        content=content,
                        el=post_el,
                        content_el=content_el,  # type: ignore
                    )
                )
            return posts

        def purge(
            id: str, listing=False, equips=False, mats=False, fails=False
        ) -> None:
            # fmt: off
            with DB:
                if fails: DB.execute("DELETE FROM kedama_fails_item WHERE id_auction = ?",(id,),)
                if equips: DB.execute("DELETE FROM kedama_equips WHERE id_auction = ?",(id,),)
                if mats: DB.execute("DELETE FROM kedama_mats WHERE id_auction = ?",(id,),)
                if listing: DB.execute("DELETE FROM kedama_auctions WHERE id = ?",(id,),)
            # fmt: on

        return await main()

    @classmethod
    def _parse_thread(cls, auction_id: str, thread: list[_Post]) -> dict[str, Any]:
        """Get items being auctioned

        Returns a dict with the following keys:
            mats:       list[dict] with keys matching DB table
            equips:     list[dict] with keys matching DB table
            fails:      dict with the following keys: [id, id_auction, summary]
        """

        # The unit suffix for prices (\d+[mkc] ~ 50000c) isn't optional because
        # there are users with purely numbers for their ign
        # and Kedama probably wouldn't write 50000
        # fmt: off
        ITEM_CODE_PATT = re.compile(r"\[([a-z]+)(\d+)\]", re.IGNORECASE)  # [Mat01]
        LEVEL_PATT = re.compile(r'(?:Lv)?[\s.]*(\d+|Unassigned),?', re.IGNORECASE) # Lv.406
        SELLER_PATT = re.compile(r"seller:\s*(.*)", re.IGNORECASE)  # (seller: rokyroky)
        START_BID_PATT = re.compile(r'start:\s*(\d+.?\d*[mkc])', re.IGNORECASE) # start:100m
        BUYER_PATT = re.compile(r"(?:(.*) (\d+.?\d*[mkc])\s*#(\d+))", re.IGNORECASE)  # magiclamp 250k #9
        QUANT_NAME_PATT = re.compile(r"(\d+)x?\s*([^()]*)", re.IGNORECASE)  # 50x Binding of the Owl
        # fmt: on

        def main():
            logger.info(f"Parsing auction {auction_id}")

            # Find the first N post(s) with auction items
            item_posts: list[_Post] = []
            for post in thread:
                if post.author_id != cls.KEDAMA_ID:
                    break
                item_posts.append(post)
            assert len(item_posts) > 0

            # Filter and parse rows describing an item for sale
            rows: list[list[_StrWithHref]] = []
            for post in item_posts:
                rows.extend(post.content)

            item_data: dict[str, list[dict]] = dict(mats=[], equips=[], fails=[])
            for r in rows:
                text = "".join(str(x) for x in r).strip()
                if m := ITEM_CODE_PATT.match(text):
                    # Handle exceptional lines
                    match parse_quirky_row(auction_id, r):
                        case result, is_mat:
                            type = "mats" if is_mat else "equips"
                            item_data[type].append(result)
                            continue
                        case "SKIP":
                            continue
                        case None:
                            pass

                    # Otherwise parse normally
                    try:
                        result, is_mat = parse_row(auction_id, r)
                        type = "mats" if is_mat else "equips"
                        item_data[type].append(result)
                    except:
                        logger.exception(f"Failed to parse line: {text}")
                        item_data["fails"].append(
                            dict(
                                id="".join(m.groups()),
                                id_auction=auction_id,
                                summary=text,
                            )
                        )

            return item_data

        def parse_row(auction_id: str, line: list[_StrWithHref]) -> tuple[dict, bool]:
            result = dict()
            urls = [x.href for x in line if x.href]

            ((cat, cat_index), rem) = match_and_subtract(line[0].text, ITEM_CODE_PATT)  # type: ignore
            if cat.lower() == "mat":
                assert len(line) == 1, line
                assert len(urls) == 0, urls

                result = parse_mat_row(rem)
                is_mat = True
            else:
                assert rem.strip() == "", rem
                assert len(line) == 3, line
                assert len(urls) == 1, urls
                result = parse_equip_row(line[1], line[2].text)
                is_mat = False

            result["id"] = f"{cat}{cat_index}"
            result["id_auction"] = auction_id
            return result, is_mat

        def parse_equip_row(url: _StrWithHref, text: str) -> dict:
            rem = text
            result: dict[str, Any] = dict(name=url.text)

            # Extract equip eid / key
            [eid, key, is_isekai] = parse_equip_link(url.href)  # type: ignore
            result["eid"] = eid
            result["key"] = key
            result["is_isekai"] = is_isekai

            # The level and stats should be parenthesized, possibly separately
            # And if the seller is listed, then they should have be parenthesized separately
            grps, rem = get_parenthesized(rem)

            # Extract seller
            for g in grps.copy():
                match match_and_subtract(g, SELLER_PATT):
                    case None:
                        continue
                    case ((seller,), rem_):
                        assert rem_.strip() == "", rem_
                        grps.remove(g)
                        result["seller"] = seller.strip()
                        break
                    case _:
                        raise AssertionError(text)
            else:
                result["seller"] = None

            # Extract level
            for i, g in enumerate(grps.copy()):
                match match_and_subtract(g, LEVEL_PATT):
                    case None:
                        pass
                    case ((level,), rem_):
                        if rem_.strip() == "":
                            grps.remove(g)
                        else:
                            grps[i] = rem_

                        if level.lower() == "unassigned":
                            result["level"] = 0
                        else:
                            result["level"] = int(level)

                        break
                    case _:
                        raise AssertionError(text)
            else:
                raise AssertionError(text)

            # Extract stats
            match grps:
                case [stats]:
                    result["stats"] = json.dumps([x.strip() for x in stats.split(",")])
                case []:
                    result["stats"] = "[]"
                case [stats, *rest]:
                    result["stats"] = json.dumps([x.strip() for x in stats.split(",")])
                    logger.debug(f"Discarding parenthesized text: {rest}")

            # Extract start_bid
            match match_and_subtract(rem, START_BID_PATT):
                case ((start_bid,), rem_):
                    result["start_bid"] = price_to_int(start_bid)
                    rem = rem_
                case _:
                    result["start_bid"] = None

            # Extract buyer
            match match_and_subtract(rem, BUYER_PATT):
                case ((buyer, price, post_index), rem_):
                    rem = rem_
                    result["buyer"] = buyer.strip()
                    result["price"] = price_to_int(price)
                    result["post_index"] = int(post_index)
                case _:
                    result["buyer"] = None
                    result["price"] = None
                    result["post_index"] = None

            rem = rem.strip()
            if len(rem) >= 10:
                logger.warning(f"Remainder is [{rem}] from [{text}]")
            elif rem:
                logger.trace(f"Remainder is [{rem}] from [{text}]")

            return result

        def parse_mat_row(text: str) -> dict:
            rem = text
            result: dict[str, Any] = dict()

            # Extract name and quantity
            match match_and_subtract(rem, QUANT_NAME_PATT):
                case ((quantity, name), rem_):
                    result["name"] = name.strip()
                    result["quantity"] = int(quantity)
                    rem = rem_
                case _:
                    raise AssertionError(rem)

            # Extract seller
            grps, rem = get_parenthesized(rem)
            match grps:
                case []:
                    result["seller"] = None
                case [seller, *rest]:
                    match match_and_subtract(grps[0], SELLER_PATT):
                        case None:
                            result["seller"] = None
                            if rest:
                                logger.debug(f"Discarding parenthesized text: {rest}")
                        case ((seller,), rem_):
                            assert rem_.strip() == "", rem_
                            result["seller"] = seller.strip()
                            if rest:
                                logger.debug(f"Discarding parenthesized text: {rest}")
                        case _:
                            raise AssertionError(text)

            # Extract start_bid
            match match_and_subtract(rem, START_BID_PATT):
                case ((start_bid,), rem_):
                    result["start_bid"] = price_to_int(start_bid)
                    rem = rem_
                case _:
                    result["start_bid"] = None

            # Extract buyer
            match match_and_subtract(rem, BUYER_PATT):
                case ((buyer, price, post_index), rem_):
                    rem = rem_
                    result["buyer"] = buyer.strip()
                    result["price"] = price_to_int(price)
                    result["unit_price"] = result["price"] / result["quantity"]
                    result["post_index"] = int(post_index)
                case _:
                    result["buyer"] = None
                    result["price"] = None
                    result["unit_price"] = None
                    result["post_index"] = None

            rem = rem.strip()
            if len(rem) >= 10:
                logger.warning(f"Remainder is [{rem}] from [{text}]")
            elif rem:
                logger.trace(f"Remainder is [{rem}] from [{text}]")

            return result

        def parse_quirky_row(
            auction_id: str, line: list[_StrWithHref]
        ) -> tuple[dict, bool] | Literal["SKIP"] | None:
            """Skip certain lots or update the text so that they can be parsed

            This isn't try-catched so verify this actually works and only affects the intended lot
            """

            text = "".join(str(x) for x in line).strip()

            # Hard-coded exceptions
            match auction_id:
                case "232564":
                    if text.startswith("[One02]"):
                        logger.debug(f'Fixing "lseller": {text}')
                        line[2].text = line[2].text.replace("lseller", "seller")
                        return parse_row(auction_id, line)
                case "223227":
                    if text.startswith("[Clo05]"):
                        logger.debug(f'Fixing "200k50k": {text}')
                        line[2].text = line[2].text.replace("200k50k", "200k 50k")
                        return parse_row(auction_id, line)
                case "210470":
                    if text.startswith("[One11]"):
                        logger.debug(f"Fixing bid value: {text}")
                        line[2].text = line[2].text.replace("2604629", "2604.629k")
                        return parse_row(auction_id, line)
                case "209937":
                    if text.startswith("[Clo02]"):
                        logger.debug(f"Fixing bid value: {text}")
                        line[2].text = line[2].text.replace("4888888", "4888.888k")
                        return parse_row(auction_id, line)
                case "208398":
                    if text.startswith("[Clo01]"):
                        logger.debug(f"Fixing bid value: {text}")
                        line[2].text = line[2].text.replace("1923033", "1923.033k")
                        return parse_row(auction_id, line)
                case "203451":
                    if text.startswith("[Hea41]"):
                        logger.debug(f"Fixing spacing: {text}")
                        line[2].text = line[2].text.replace(
                            "Maozi。300k", "Maozi。 300k "
                        )
                        return parse_row(auction_id, line)
                case "199165":
                    if text.startswith("[Clo22]"):
                        logger.debug(f"Fixing post number: {text}")
                        line[2].text = line[2].text.replace("22m", "22m #64")
                        return parse_row(auction_id, line)

                # First auction ¯\_(ツ)_/¯
                case "198105":
                    # Replace 99# with #99
                    if any(
                        text.startswith(f"[{x}]")
                        for x in "One08 One10 One13 Shd01 Clo35".split(" ")
                    ):
                        logger.debug(f'Fixing auction #1": {text}')
                        line[2].text = re.sub(r" (\d+)#", r" #\1", line[2].text)
                        return parse_row(auction_id, line)

                    # Fix extraneous line break
                    if text.startswith("[One10]"):
                        logger.debug(f'Fixing auction #1": {text}')
                        line[0].text += "200k #94"
                        return parse_row(auction_id, line)

                    # Fix missing post number
                    if text.startswith("[Clo33]"):
                        logger.debug(f'Fixing auction #1": {text}')
                        line[2].text += " #77"
                        return parse_row(auction_id, line)
                    if text.startswith("[M03]"):
                        logger.debug(f'Fixing auction #1": {text}')
                        line[0].text = (
                            line[0]
                            .text.replace("M03", "Mat03")
                            .replace("1.42m", "1.42m #26")
                        )
                        return parse_row(auction_id, line)

                    # Fix missing post number
                    if text.startswith("[Lig10]"):
                        logger.debug(f'Fixing auction #1": {text}')
                        line[2].text = line[2].text.replace(
                            "EvertonBNU 100k 76", "EvertonBNU 100k #76"
                        )
                        return parse_row(auction_id, line)

            # Ignore lines like "[Mat01] canceled"
            if re.search(r"\[.+\]\s*(?:delete|cancel)", text, re.IGNORECASE):
                logger.info(f"Skipping cancelled lot: {text}")
                return "SKIP"

            # Noramlize prefixes for material lots
            # [M##] -> [Mat9##]
            if re.search(r"\[M(\d+)\]", text):
                logger.debug(f"Renaming M-lot: {text}")
                line[0].text = re.sub(r"\[M(\d+)\]", r"[Mat\1]", line[0].text)
                return parse_row(auction_id, line)
            # [sp##] -> [Mat9##]
            if re.search(r"\[sp\d+\]", text):
                logger.debug(f"Renaming sp-lot: {text}")
                line[0].text = re.sub(r"\[sp(\d+)\]", r"[Mat9\1]", line[0].text)
                return parse_row(auction_id, line)
            # [V##] -> SKIP -- buyer data is on different line
            if re.search(r"\[V\d+\]", text):
                logger.debug(f"Skipping V-lot: {text}")
                return "SKIP"

            # Skip packs
            if re.search(r"\bpack\b", text, re.IGNORECASE):
                logger.info(f"Skipping pack: {text}")
                return "SKIP"

        def match_and_subtract(
            text: str, patt: re.Pattern
        ) -> tuple[tuple[str], str] | None:
            m = patt.search(text)
            if m is None:
                return None

            rem = text[: m.start()] + text[m.end() :]
            return (m.groups(), rem)

        def get_parenthesized(text: str) -> tuple[list[str], str]:
            """Find substrings surrounded by parentheses. Does not handle nested parentheses."""

            rem = text
            matches = []
            while True:
                m = match_and_subtract(rem, re.compile(r"\(([^\)]*)\)"))
                if m is None:
                    break

                matches.append(m[0][0])
                rem = m[1]

            return matches, rem

        return main()

    @classmethod
    async def _fetch_auction_urls(cls) -> list[URL]:
        """Get list of auctions

        This is expensive and unlikely to change so probably better to replace with test/stubs/kedama.py
        (since kedama quit auctioneering)
        """

        from test.stubs.kedama import AUCTION_URLS; return AUCTION_URLS  # fmt: skip

        async def main():
            session = await cls._create_session()

            # Get first page of search results
            pages = [await fetch_first_page(session)]

            # Get remaining pages
            pages.extend(
                [
                    await do_get(url, session=session, content_type="html")
                    for url in get_other_pages(pages[0])
                ]
            )

            # Extract thread urls
            await session.close()
            auction_urls = extract_thread_urls(pages)
            return auction_urls

        async def fetch_first_page(session: ClientSession) -> BeautifulSoup:
            """Search forum for Kedama's auctions and return page 1"""
            from test.stubs.kedama import TMP_SEARCH; return BeautifulSoup(TMP_SEARCH, 'lxml')  # fmt: skip

            url = URL("https://forums.e-hentai.org/index.php?act=Search&CODE=01")
            data = {
                "keywords": "[Auction]",
                "namesearch": cls.KEDAMA_IGN,
                "forums[]": "77",
                "searchsubs": "1",
                "prune": "0",
                "prune_type": "newer",
                "sort_key": "last_post",
                "sort_order": "desc",
                "search_in": "titles",
                "result_type": "topics",
            }
            soup: BeautifulSoup = await do_post(
                url, data=data, session=session, content_type="html"
            )

            link = soup.select_one(".redirectfoot > a")
            assert link
            href = link["href"]
            assert href

            href_decoded = str(href).replace("&amp;", "&")
            assert "act=Search" in href_decoded, href_decoded
            assert "searchid=" in href_decoded, href_decoded

            page: BeautifulSoup = await do_get(
                href_decoded, session=session, content_type="html"
            )
            return page

        def get_other_pages(page_one: BeautifulSoup) -> list[URL]:
            """Get url for each page in search results"""

            # Find paginator
            paginator = page_one.select_one(".pagelink")
            if not paginator:
                return []
            paginator = paginator.parent

            # Find url of last page
            last_page_el = paginator.select_one(".pagelinklast > a")  # type: ignore
            if last_page_el is None:
                # If absent, this means all the page links are visible
                page_els = paginator.select(".pagelink > a:not([title='Next page'])")  # type: ignore
                page_urls = [URL(str(a["href"])) for a in page_els]
                return page_urls

            last_page_url = URL(str(last_page_el["href"]))
            assert "st" in last_page_url.query

            # Guess page count based on the &st=## offset of last page
            last_offset = int(last_page_url.query["st"])
            assert last_offset % cls.SEARCH_PAGE_SIZE == 0
            num_pages = 1 + last_offset // cls.SEARCH_PAGE_SIZE

            # Create urls for other pages
            base_url = last_page_url
            urls = [base_url % dict(st=i * 25) for i in range(1, num_pages)]
            return urls

        def extract_thread_urls(pages: list[BeautifulSoup]) -> list[URL]:
            """Grab url for each search result

            Args:
                pages: Search result pages
            """

            auction_urls: list[URL] = []

            for soup in pages:
                title_els = soup.select(
                    # :not([valign]) filters the sticky icon
                    # :not([title]) filters the other icons (paperclip / pagination)
                    ".ipbtable .ipbtable td:not([valign]) > a:not([title])"
                )
                assert len(title_els) == cls.SEARCH_PAGE_SIZE or soup is pages[-1]

                for a in title_els:
                    url = URL(str(a["href"]))

                    thread_id = url.query.get("showtopic")
                    assert thread_id is not None

                    normalized = url.with_query(showtopic=thread_id).with_fragment(None)
                    auction_urls.append(normalized)

            return auction_urls

        return await main()

    @classmethod
    async def _create_session(cls) -> ClientSession:
        secrets = load_toml(paths.SECRETS_FILE).value
        cookies = {k: str(v) for k, v in secrets["EH_COOKIES"].items()}

        session = create_session()
        session.cookie_jar.update_cookies(cookies)
        return session


@dataclass
class _StrWithHref:
    text: str
    href: Optional[str]

    def __str__(self):
        return self.text


class _PostParser:
    class NEWLINE:
        pass  # poor mans singleton

    @classmethod
    def parse(cls, post: Tag) -> list[list[_StrWithHref]]:
        """Split the post content into rows, ideally like it would look in the browser

        We assume post contains only inline elements like <a>, with the exception of <br>
        The returned value describes the text content of each line, while retaining any hrefs
        """

        parts = cls._parse(post)

        # Split by <br>
        rows: list[list[_StrWithHref]] = split_lst(parts, lambda x: x is cls.NEWLINE)

        # Simplify by joining consecutive fragments without an href
        result = []
        for row in rows:
            if len(row) == 0:
                result.append([])
                continue

            buffer = None
            new_row = []
            for frag in row:
                if frag.href:
                    if buffer:
                        new_row.append(buffer)
                        buffer = None
                    new_row.append(frag)
                    continue
                else:
                    if buffer:
                        buffer.text += frag.text
                    else:
                        buffer = copy.deepcopy(frag)

            if buffer:
                new_row.append(buffer)

            result.append(new_row)

        return result

    @classmethod
    def _parse(cls, post: Tag) -> list[_StrWithHref | Type[NEWLINE]]:
        """Get a list of [some_text, some_text, NEWLINE, some_text, NEWLINE, ...]"""

        result = []
        for child in post.children:
            if isinstance(child, Tag):
                if child.name == "br":
                    result.append(cls.NEWLINE)
                elif child.name == "a" and child.get("href"):
                    result.append(
                        _StrWithHref(text=child.text, href=str(child["href"]))
                    )
                else:
                    result.extend(cls._parse(child))
            else:
                result.append(_StrWithHref(text=child.text, href=None))
        return result


if __name__ == "__main__":
    # fmt: off
    import asyncio
    async def main():
        await KedamaScraper.update()
    asyncio.run(main())
