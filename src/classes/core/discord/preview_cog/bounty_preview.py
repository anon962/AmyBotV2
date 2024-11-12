import datetime
import re

import aiohttp
import loguru
import yarl
from bs4 import BeautifulSoup, Tag

from config import paths
from utils.html import (
    get_attr_or_raise,
    get_stripped_text,
    search_or_raise,
    select_one_or_raise,
)
from utils.misc import load_toml

LOGGER = loguru.logger.bind(tags=["discord_bot"])


def extract_bounty_links(text: str) -> list[dict]:
    # https://e-hentai.org/bounty.php?bid=21180
    m_urls: list[tuple[str | None, str]] = re.findall(
        r"(!?)([^\s]*e-hentai.org/bounty[^\s]+)", text
    )

    bounties = []
    for prefix, url_text in m_urls:
        try:
            url = yarl.URL(url_text)
        except Exception:
            continue

        # Bounty id
        bid = url.query.get("bid")
        if bid is None:
            continue
        try:
            bid = int(bid)
        except ValueError:
            continue

        bounties.append(
            dict(
                bid=bid,
                is_expanded=bool(prefix),
            )
        )

    return bounties


async def fetch_bounty_page(bid: int) -> tuple[BeautifulSoup, str] | tuple[None, None]:
    session = _init_hv_session()

    url = f"https://e-hentai.org/bounty.php?bid={bid}"

    try:
        LOGGER.info(f"Fetching {url}")
        resp = await session.get(url)
        LOGGER.info(f"{resp.status} for {url}")

        if resp.status != 200:
            return None, None

        html = await resp.text()
    finally:
        await session.close()

    return BeautifulSoup(html, "lxml"), str(url)


def parse_bounty_page(soup: BeautifulSoup) -> dict:
    title_el = select_one_or_raise(soup, "h1")
    title = get_stripped_text(title_el)

    description_el = select_one_or_raise(soup, "#x")
    description = _parse_bounty_description(description_el)

    header_rows = soup.select("#d tr")
    headers = dict()
    for el in header_rows:
        headers.update(_parse_header_row(el))

    return dict(
        title=title,
        description=description,
        headers=headers,
    )


def format_bounty_preview(config: dict, bounty: dict, is_expanded: bool):
    max_length_mult = config["expansion_multiplier"] if is_expanded else 1

    title = bounty["title"]
    title = _truncate(title, config["max_title_length"] * max_length_mult)

    bounty_type = bounty["headers"]["type"]
    status = bounty["headers"]["status"].replace("Closed/Completed", "Closed")

    reward = bounty["headers"]["reward"]
    credits_value = reward["credits"] + config["hath_value"] * reward["hath"]
    credits_value_str = _humanize_credits_value(credits_value)
    if reward["hath"] > 0:
        credits_value_str = "~" + credits_value_str

    # [ Translation | ~6.5m Credits | Closed/Completed ]
    body_header = f"[ {bounty_type} | {credits_value_str} | {status} ]"

    body_description = bounty["description"]
    body_description = _truncate(
        body_description,
        config["max_body_length"] * max_length_mult,
        f"\n\n[...]",
    )

    # by 프레이 | 2020-07-28
    author = bounty["headers"]["author"]
    author_name = author["name"]
    author_url = f"https://e-hentai.org/bounty.php?u={author['uid']}"
    body_footer = f"by [{author_name}]({author_url})"
    body_footer += " | " + bounty["headers"]["date"]["created_at"].strftime(r"%Y-%m-%d")

    body = "```css\n" + body_header + "\n\n" + body_description + "```\n" + body_footer

    return title, body


def _parse_header_row(el: Tag) -> dict:
    name_el = el.select_one(".l")
    if not name_el:
        LOGGER.warning(f"Unparseable bounty header: {str(el)}")
        return dict()

    name = get_stripped_text(name_el)

    value_el = el.select_one(".r")
    if not value_el:
        LOGGER.warning(f"Unparseable bounty header: {str(el)}")
        return dict()

    if name == "Bounty Posted By:":
        author_el = select_one_or_raise(value_el, "a")

        author_name = get_stripped_text(author_el)

        uid = int(
            search_or_raise(
                r"https://e-hentai.org/bounty.php\?u=(\d+)",
                get_attr_or_raise(author_el, "href"),
            ).group(1)
        )

        return dict(
            author=dict(
                uid=uid,
                name=author_name,
            )
        )
    elif name == "Posted Date:":
        # 2020-07-28 10:20 (Updated: 2020-11-13 00:31)
        m = search_or_raise(
            r"(\d+)-(\d+)-(\d+) (\d+):(\d+) (?:\(\s*Updated\s*: (\d+)-(\d+)-(\d+) (\d+):(\d+))\)",
            get_stripped_text(value_el),
        )

        (
            year,
            month,
            day,
            hour,
            minute,
            up_year,
            up_month,
            up_day,
            up_hour,
            up_minute,
        ) = [int(x) for x in m.groups() if x is not None]

        created_at = datetime.datetime(
            year=year, month=month, day=day, hour=hour, minute=minute
        )

        updated_at = None
        if up_year is not None:
            updated_at = datetime.datetime(
                year=up_year, month=up_month, day=up_day, hour=up_hour, minute=up_minute
            )

        return dict(
            date=dict(
                created_at=created_at,
                updated_at=updated_at,
            )
        )
    elif name == "Bounty Type:":
        return dict(type=get_stripped_text(value_el))
    elif name == "Bounty Status:":
        return dict(status=get_stripped_text(value_el))
    elif name == "Min Hunter Rank:":
        return dict(min_rank=get_stripped_text(value_el))
    elif name == "Current Reward:":
        reward_text = get_stripped_text(value_el)

        # 5,565,000 Credits + 257 Hath
        m = search_or_raise(
            r"(?:([\d,]+) Credits)?(?: \+ )?(?:([\d,]+) Hath)?", reward_text
        )
        credits_text, hath_text = m.groups()
        credits = int(credits_text.replace(",", "")) if credits_text else 0
        hath = int(hath_text.replace(",", "")) if hath_text else 0

        return dict(
            reward=dict(
                credits=credits,
                hath=hath,
            )
        )
    elif name == "Accepted Delivery:":
        pass
    else:
        LOGGER.warning(f"Unknown bounty header: {str(el)}")

    return dict()


def _init_hv_session():
    secrets = load_toml(paths.SECRETS_FILE).value
    cookies = {k: str(v) for k, v in secrets["HV_COOKIES"].items()}

    session = aiohttp.ClientSession(cookies=cookies)

    return session


def _humanize_credits_value(credits: int) -> str:
    if credits >= 10**6:
        val = credits / 10**6
        unit = "m"
        digits = 1
    elif credits >= 10**3:
        val = credits / 10**6
        unit = "k"
        digits = 0
    else:
        val = credits
        unit = "c"
        digits = 0

    return f"{val:.{digits}f}{unit}"


def _truncate(text: str, max_length: int, trailer="..."):
    if len(text) > max_length:
        text = text[:max_length]
        text = text[: -len(trailer)] + trailer
    return text


def _parse_bounty_description(el: Tag) -> str:
    text = ""

    for child_el in el.contents:
        if isinstance(child_el, Tag) and child_el.name == "br":
            text += "\n"
        else:
            text += get_stripped_text(child_el)

    return text
