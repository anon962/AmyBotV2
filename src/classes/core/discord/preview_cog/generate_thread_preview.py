import asyncio
import datetime
import re
from dataclasses import dataclass

import aiohttp
import loguru
import tomli
import yarl
from bs4 import BeautifulSoup, Tag
from PIL import Image

from config.paths import CONFIG_DIR
from utils.html import (
    get_attr_or_raise,
    get_self_text,
    get_stripped_text,
    search_or_raise,
    select_one_or_raise,
)
from utils.misc import download_image

LOGGER = loguru.logger.bind(tags=["discord_bot"])


def extract_thread_links(text: str):
    m_urls: list[tuple[str | None, str]] = re.findall(
        r"(!?)([^\s]+forums\.e-hentai\.org[^\s]*)", text
    )
    print(m_urls)

    threads = []
    for prefix, url_text in m_urls:
        try:
            url = yarl.URL(url_text)
        except Exception:
            continue

        # Thread id
        tid = url.query.get("showtopic")
        if tid is None:
            continue
        try:
            tid = int(tid)
        except ValueError:
            continue

        # Post index
        st = url.query.get("st")
        if st is not None:
            try:
                st = int(st)
            except ValueError:
                continue

        # Post id
        pid = url.query.get("p")
        if pid is not None:
            try:
                pid = int(pid)
            except ValueError:
                continue

        view = url.query.get("view")
        find_post = view and view == "findpost"

        threads.append(
            dict(
                tid=tid,
                st=st,
                pid=pid,
                find_post=find_post,
                is_expanded=bool(prefix),
            )
        )

    return threads


def format_thread_preview(
    thread: dict,
    is_expanded: bool,
    target_pid: int | None = None,
):
    config = tomli.loads((CONFIG_DIR / "preview_config.toml").read_text())
    target_post = find_target_post(thread, target_pid) or thread["posts"][0]

    length_mult = config["expansion_multiplier"] if is_expanded else 1

    title = _truncate(
        thread["title"],
        length_mult * config["max_title_length"],
    )

    sub_title = thread["description"]

    body_parts = []
    for p in target_post["body_parts"]:
        if p["type"] in ["quotetop", "quotemain"]:
            body_parts.append(f"[quote]...[/quote]")
        elif p["type"] in ["edit"]:
            pass
        else:
            body_parts.append(p["text"])

    post_body = "\n".join(body_parts)
    post_body = re.sub("\n\n", "\n", post_body)
    post_body = _truncate(
        post_body,
        length_mult * config["max_body_length"],
    )
    post_body = post_body or "(This space intentionally left blank)"

    # by qw3rty67 | 2018-01-15 | The HentaiVerse Chat
    author = target_post["author"]
    author_url = f'https://forums.e-hentai.org/index.php?showuser={author["uid"]}'
    footer = f"by [{author['name']}]({author_url})"

    date = target_post["date"]
    footer += " | " + date.strftime(r"%Y-%m-%d")

    forum_name = _truncate(thread["forum"]["name"], 15)
    footer += f" | [{forum_name}]({thread['forum']['href']})"

    body = sub_title + f"\n```fix\n{post_body}\n```\n" + footer

    return title, body


async def fetch_thread(
    tid: int,
    index_start: int | None,
    pid: int | None,
    find_post=False,
) -> tuple[BeautifulSoup, str] | None:
    url = yarl.URL("https://forums.e-hentai.org/index.php")

    query = dict(showtopic=str(tid))
    if index_start is not None:
        query["st"] = str(index_start)
    if pid is not None:
        query["p"] = str(pid)
    if find_post:
        query["view"] = "findpost"

    url = url.with_query(query)

    async with aiohttp.ClientSession() as session:
        LOGGER.info(f"Fetching {url}")
        resp = await session.get(url)
        LOGGER.info(f"{resp.status} for {url}")

        if resp.status != 200:
            return None

        html = await resp.text()

    return BeautifulSoup(html, "lxml"), str(url)


async def fetch_user_thumbnail(uid: int) -> dict | None:
    candidates = [
        f"https://forums.e-hentai.org/uploads/av-{uid}.{ext}" for ext in ["jpg", "png"]
    ]

    for url in candidates:
        try:
            print("Fetching thumbnail", url)
            im = await download_image(url)
            return dict(im=im, url=url)
        except ValueError:
            continue

    return None


def parse_thread(soup: BeautifulSoup) -> dict:
    title_desc_el = select_one_or_raise(soup, ".maintitle div")
    title = get_stripped_text(select_one_or_raise(title_desc_el, "b"))
    description = get_self_text(title_desc_el).strip(", ")

    forum_el = select_one_or_raise(soup, "#navstrip > a:last-child")
    forum_name = get_stripped_text(forum_el)
    forum_href = get_attr_or_raise(forum_el, "href")

    post_els = soup.select("div:not(#topicoptionsjs) > .borderwrap > table")
    posts = [_parse_post(el) for el in post_els]

    return dict(
        title=title,
        description=description,
        posts=posts,
        forum=dict(
            name=forum_name,
            href=forum_href,
        ),
    )


def _parse_post(post_el: Tag) -> dict:
    date_el = select_one_or_raise(post_el, ".subtitle span")
    date_text = get_stripped_text(date_el)
    date = _parse_date(date_text)

    author_el = select_one_or_raise(post_el, ".bigusername > a")
    author_name = get_stripped_text(author_el)
    author_url = yarl.URL(get_attr_or_raise(author_el, "href"))
    author_id = int(author_url.query.getone("showuser"))

    body_parts = []
    body_el = select_one_or_raise(post_el, ".postcolor")
    for child_el in body_el.contents:
        part_type = "plaintext"
        if isinstance(child_el, Tag):
            classes = child_el.get("class", [])
            if "quotetop" in classes:
                part_type = "quotetop"
            elif "quotemain" in classes:
                part_type = "quotemain"
            elif "edit" in classes:
                part_type = "edit"

        body_parts.append(
            dict(
                type=part_type,
                text=get_stripped_text(child_el),
            )
        )

    post_index_el = select_one_or_raise(post_el, ".postdetails > a")
    post_index = int(
        search_or_raise(
            r"#(\d+)",
            get_stripped_text(post_index_el),
        ).group(1)
    )
    post_id = int(
        search_or_raise(
            r"link_to_post\((\d+)\)",
            get_attr_or_raise(post_index_el, "onclick"),
        ).group(1)
    )

    return dict(
        pid=post_id,
        index=post_index,
        date=date,
        author=dict(
            name=author_name,
            uid=author_id,
        ),
        body_parts=body_parts,
    )


def _parse_date(date_text: str):
    MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

    if date_text.startswith("Today"):
        # Today, 12:58
        hr, min = search_or_raise(r"Today, (\d+):(\d+)", date_text).groups()
        date = datetime.datetime.today().replace(hour=int(hr), minute=int(min))
    elif date_text.startswith("Yesterday"):
        # Yesterday, 23:17
        hr, min = search_or_raise(r"Yesterday, (\d+):(\d+)", date_text).groups()
        date = datetime.datetime.today().replace(hour=int(hr), minute=int(min))
        date = date.replace(day=date.day - 1)
    else:
        # Jul 27 2020, 12:06
        month, day, year, hr, min = search_or_raise(
            r"(\w+) (\d+) (\d+), (\d+):(\d+)", date_text
        ).groups()

        date = datetime.datetime(
            year=int(year),
            month=1 + MONTHS.index(month),
            day=int(day),
            hour=int(hr),
            minute=int(min),
        )

    return date


def _truncate(text: str, max_length: int, trailer="..."):
    if len(text) > max_length:
        text = text[:max_length]
        text = text[: -len(trailer)] + trailer
    return text


def find_target_post(thread: dict, pid: int | None) -> dict:
    posts_by_pid = {p["pid"]: p for p in thread["posts"]}
    target_post = posts_by_pid.get(pid, None)
    return target_post
