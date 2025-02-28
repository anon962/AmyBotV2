import asyncio
import io
import time
from dataclasses import dataclass
from typing import Any

import tomli
from discord import Embed, File, Message
from discord.ext import commands
from PIL import Image

from classes.core import discord
from classes.core.discord import types as types
from classes.core.discord.discord_watchers import DeleteWatcher, EditWatcher
from classes.core.discord.preview_cog.bounty_preview import (
    extract_bounty_links,
    fetch_bounty_page,
    format_bounty_preview,
    parse_bounty_page,
)
from classes.core.discord.preview_cog.equip_preview import (
    extract_equip_links,
    generate_equip_preview,
)
from classes.core.discord.preview_cog.thread_preview import (
    extract_thread_links,
    fetch_super_auction_info,
    fetch_thread,
    fetch_user_thumbnail,
    find_target_post,
    format_thread_preview,
    parse_thread,
)
from config import logger
from config.paths import CONFIG_DIR

LOGGER = logger.bind(tags=["discord_bot"])


@dataclass
class PreviewCog(commands.Cog):
    bot: "discord.AmyBot"

    THREAD_FETCH_DELAY = 2
    BOUNTY_FETCH_DELAY = 2

    def __init__(self, bot, *args: Any) -> None:
        super().__init__(*args)

        self.bot = bot

        self.last_thread_fetch = 0
        self.last_bounty_fetch = 0

    @commands.Cog.listener()
    async def on_message(self, msg: Message):
        if msg.author.id == self.bot.user.id:  # type: ignore
            return

        await self.scan_equip_previews(msg)
        await self.scan_thread_previews(msg)
        await self.scan_bounty_previews(msg)

    async def scan_equip_previews(self, msg: Message):
        links = extract_equip_links(msg.content)
        if not links:
            return

        async with msg.channel.typing():
            equip_previews, has_fail = generate_equip_preview(links)
            if has_fail:
                await msg.add_reaction("❌")

            if not equip_previews:
                return

            response = await msg.channel.send("".join(equip_previews))

        self.bot.watcher_cog.register(
            await EditWatcher(
                msg.id, [response.id], msg.channel.id, self.bot
            ).__ainit__()
        )
        self.bot.watcher_cog.register(
            await DeleteWatcher(
                msg.id, [response.id], msg.channel.id, self.bot
            ).__ainit__()
        )

    async def scan_thread_previews(self, msg: Message):
        matches = extract_thread_links(msg.content)
        if not matches:
            return

        async with msg.channel.typing():
            has_fail = False
            for m in matches:
                # Rate limit
                delay, self.last_thread_fetch = _calc_delay(
                    self.last_thread_fetch, self.THREAD_FETCH_DELAY
                )
                if delay > 0:
                    await asyncio.sleep(delay)

                # Fetch thread
                r = await fetch_thread(
                    m["tid"],
                    m["st"],
                    m["pid"],
                    find_post=m["find_post"],
                )
                if not r:
                    has_fail = True
                    continue

                # Parse thread
                soup, url = r
                thread = parse_thread(soup)

                target_post = find_target_post(thread, m["pid"]) or thread["posts"][0]

                auction_info = None
                if (
                    "auction" in thread["title"].lower()
                    and target_post is thread["posts"][0]
                    and target_post["author"]["name"] == "Superlatanium"
                ):
                    try:
                        auction_info = await fetch_super_auction_info(
                            self.bot.api_url, m["tid"]
                        )
                    except Exception:
                        LOGGER.exception("Preview for super auction failed")

                # Format embed text
                title, description = format_thread_preview(
                    thread,
                    auction_info,
                    m["is_expanded"],
                    m["pid"],
                )

                embed = Embed(
                    title=title,
                    description=description,
                    url=url,
                )

                # Add thumbnail
                file = None
                if not auction_info:
                    thumbnail = await fetch_user_thumbnail(target_post["author"]["uid"])

                    if thumbnail:
                        embed.set_thumbnail(url="attachment://image.png")
                        file = _get_thumbnail_file(thumbnail["im"])

                # Send
                await msg.channel.send(embed=embed, file=file)  # type: ignore

            # Notify error
            if has_fail:
                await msg.add_reaction("❌")

    async def scan_bounty_previews(self, msg: Message):
        links = extract_bounty_links(msg.content)
        if not links:
            return

        config = tomli.loads((CONFIG_DIR / "preview_config.toml").read_text())

        has_fail = False
        async with msg.channel.typing():
            for l in links:
                # Rate limit
                delay, self.last_bounty_fetch = _calc_delay(
                    self.last_bounty_fetch, self.BOUNTY_FETCH_DELAY
                )
                if delay > 0:
                    await asyncio.sleep(delay)

                # Fetch bounty
                soup, url = await fetch_bounty_page(l["bid"])
                if not soup:
                    continue

                # Format embed text
                try:
                    bounty = parse_bounty_page(soup)
                    title, body = format_bounty_preview(
                        config,
                        bounty,
                        l["is_expanded"],
                    )
                except Exception:
                    has_fail = True
                    LOGGER.exception("Bounty preview failed")
                    continue

                embed = Embed(
                    title=title,
                    description=body,
                    url=url,
                )

                # Add thumbnail
                file = None
                uid = bounty["headers"].get("author", dict()).get("uid", None)
                if uid:
                    thumbnail = await fetch_user_thumbnail(uid)
                    if thumbnail:
                        embed.set_thumbnail(url="attachment://image.png")
                        file = _get_thumbnail_file(thumbnail["im"])

                # Send
                await msg.channel.send(embed=embed, file=file)  # type: ignore

            # Notify error
            if has_fail:
                await msg.add_reaction("❌")

    def __hash__(self) -> int:
        return self.__class__.__name__.__hash__()


def _calc_delay(last_fetch: float, min_delay: float):
    # Rate limit
    next_fetch = last_fetch + min_delay
    now = time.time()

    last_fetch_update = max(next_fetch, now)

    delay = 0
    if next_fetch > now:
        delay = next_fetch - now

    if delay:
        LOGGER.info(f"Delaying by {delay}")

    return delay, last_fetch_update


def _get_thumbnail_file(im: Image.Image):
    buf = io.BytesIO()
    im.save(buf, format="PNG")

    buf.seek(0)
    file = File(buf, "image.png")

    return file
