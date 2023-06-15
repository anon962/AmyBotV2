from datetime import datetime, timezone, timedelta
import json
import re
from typing import Literal
from aiohttp import ClientSession

from bs4 import BeautifulSoup
from yarl import URL

from classes.db import DB
from config import logger, paths
from utils.http import create_session, do_get
from utils.json_cache import JsonCache
from utils.rate_limit import rate_limit
from utils.misc import load_toml

logger = logger.bind(tags=["lottery"])

_limit = rate_limit(calls=1, period=5, scope="hv")
do_get = _limit(do_get)


LotteryType = Literal["weapon", "armor"]

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


class LotteryScraper:
    START_WEAPON = datetime(2013, 9, 14, 0, 5, tzinfo=timezone.utc)
    START_ARMOR = datetime(2014, 3, 29, 12, 5, tzinfo=timezone.utc)

    HTML_CACHE_FILE = JsonCache(paths.CACHE_DIR / "lottery_html.json", default=dict)
    html_cache: dict = HTML_CACHE_FILE.load()  # type: ignore

    @classmethod
    async def update(cls) -> None:
        async def main():
            session = await cls._create_session()

            try:
                types: list[LotteryType] = ["weapon", "armor"]
                for type in types:
                    lotto_start = (
                        cls.START_WEAPON if type == "weapon" else cls.START_ARMOR
                    )
                    table_name = (
                        "lottery_weapon" if type == "weapon" else "lottery_armor"
                    )

                    missing = calculate_missing(type)
                    for index in missing:
                        try:
                            page = await fetch_page(index, type, session)
                        except ValueError:
                            logger.info(f"Unable to fetch lottery {type} {index}")
                            return

                        data = parse_page(page)
                        data["id"] = index

                        # Calculate timestamp
                        start_date = lotto_start + timedelta(days=index - 1)
                        # Can't assert bc weapons describe start date, armors describe end date
                        # assert start_date.month == data["month"]
                        # assert start_date.day == data["day"]
                        data["date"] = start_date.timestamp()

                        # Insert into DB
                        with DB:
                            DB.execute(
                                f"""
                                INSERT INTO {table_name}
                                (id, date, tickets, "1_prize", "1_user", "1b_prize", "1b_user", "2_prize", "2_user", "3_prize", "3_user", "4_prize", "4_user", "5_prize", "5_user")
                                VALUES (:id, :date, :tickets, :1_prize, :1_user, :1b_prize, :1b_user, :2_prize, :2_user, :3_prize, :3_user, :4_prize, :4_user, :5_prize, :5_user)
                                """,
                                data,
                            )
            finally:
                await session.close()

        def calculate_missing(type: LotteryType):
            # Get index of last completed
            now = datetime.now(timezone.utc)
            start = cls.START_WEAPON if type == "weapon" else cls.START_ARMOR
            last_completed = (now - start).days

            # Compare against index in db
            with DB:
                table = "lottery_weapon" if type == "weapon" else "lottery_armor"
                result = DB.execute(
                    f"""
                    SELECT MAX(id) FROM {table}
                    """
                ).fetchone()
                last_scanned = list(result)[0] or 0

            missing = list(range(last_scanned + 1, last_completed + 1))
            return missing

        async def fetch_page(
            id: int, type: LotteryType, session: ClientSession, allow_cached=True
        ):
            cache_id = f"{id}_{type}"

            if not allow_cached or cache_id not in cls.html_cache:
                # Fetch lottery page
                ss = "lt" if type == "weapon" else "la"
                url = URL("http://alt.hentaiverse.org") % dict(
                    s="Bazaar", ss=ss, lottery=id
                )
                html: str = await do_get(url, session=session, content_type="text")

                # If fetch not successful, we're probably in-battle
                if 'id="lotteryform"' not in html:
                    raise ValueError

                cls.html_cache[cache_id] = html
                cls.HTML_CACHE_FILE.dump(cls.html_cache)

            html = cls.html_cache[cache_id]
            page = BeautifulSoup(html, "lxml")
            return page

        def parse_page(page: BeautifulSoup) -> dict:
            result = dict()

            # Extract date
            title = page.select_one("#leftpane > div").text  # type: ignore
            title_match = re.match(r"Grand Prize for (\w+) (\d+)", title)
            result["month"] = 1 + MONTHS.index(title_match.group(1))  # type: ignore
            result["day"] = int(title_match.group(2))  # type: ignore

            # Extract ticket pool size
            rightpane_text = page.select_one("#rightpane").text  # type: ignore
            tickets = re.search(r"You hold \d+ of (\d+) sold tickets.", rightpane_text)
            result["tickets"] = int(tickets.group(1))  # type: ignore

            # Extract equip name
            result["1_prize"] = page.select_one("#lottery_eqname").text  # type: ignore
            if result["1_prize"] == "No longer available":
                result["1_prize"] = None

            # Extract winners and other prizes
            texts = [x.text for x in page.select("#leftpane > div:last-child > div")]
            assert len(texts) == 10

            def parse_prize(text: str) -> str:
                # Strip the '#th Prize: ' text
                text = re.sub(r"\d\w+ Prize: ", "", text)

                # Split '10 Chaos Tokens' into (10, 'Chaos Tokens')
                split = text.split(" ", maxsplit=1)
                return json.dumps([int(split[0]), split[1]])

            result["1_user"] = texts[0].replace("Equip Winner: ", "")
            result["1b_prize"] = "Equip Core"
            result["1b_user"] = texts[1].replace("Core Winner: ", "") or None
            result["2_prize"] = parse_prize(texts[2])
            result["2_user"] = texts[3].replace("Winner: ", "")
            result["3_prize"] = parse_prize(texts[4])
            result["3_user"] = texts[5].replace("Winner: ", "")
            result["4_prize"] = parse_prize(texts[6])
            result["4_user"] = texts[7].replace("Winner: ", "")
            result["5_prize"] = parse_prize(texts[8])
            result["5_user"] = texts[9].replace("Winner: ", "")

            return result

        return await main()

    @classmethod
    async def _create_session(cls) -> ClientSession:
        secrets = load_toml(paths.SECRETS_FILE).value
        cookies = {k: str(v) for k, v in secrets["HV_COOKIES"].items()}

        session = create_session()
        session.cookie_jar.update_cookies(cookies)
        return session


if __name__ == "__main__":

    async def main():
        await LotteryScraper.update()

    import asyncio

    asyncio.run(main())
