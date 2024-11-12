import asyncio
import io
import time
from dataclasses import dataclass
from typing import Any

from discord import Embed, File, Message
from discord.ext import commands

from classes.core import discord
from classes.core.discord import types as types
from classes.core.discord.discord_watchers import DeleteWatcher, EditWatcher
from classes.core.discord.preview_cog.generate_equip_preview import (
    extract_equip_links,
    generate_equip_preview,
)
from classes.core.discord.preview_cog.generate_thread_preview import (
    extract_thread_links,
    fetch_thread,
    fetch_user_thumbnail,
    find_target_post,
    format_thread_preview,
    parse_thread,
)
from config import logger

logger = logger.bind(tags=["discord_bot"])


@dataclass
class PreviewCog(commands.Cog):
    bot: "discord.AmyBot"

    THREAD_FETCH_DELAY = 2

    def __init__(self, bot, *args: Any) -> None:
        super().__init__(*args)

        self.bot = bot

        self.last_thread_fetch = 0

    @commands.Cog.listener()
    async def on_message(self, msg: Message):
        await self.scan_equip_previews(msg)
        await self.scan_thread_previews(msg)

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
                next_fetch = self.last_thread_fetch + self.THREAD_FETCH_DELAY
                now = time.time()

                self.last_thread_fetch = max(next_fetch, now)
                if next_fetch > now:
                    await asyncio.sleep(next_fetch - now)

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

                # Format embed text
                title, description = format_thread_preview(
                    thread, m["is_expanded"], m["pid"]
                )

                embed = Embed(
                    title=title,
                    description=description,
                    url=url,
                )

                # Add thumbnail
                file = None
                target_post = find_target_post(thread, m["pid"]) or thread["posts"][0]
                thumbnail = await fetch_user_thumbnail(target_post["author"]["uid"])
                if thumbnail:
                    embed.set_thumbnail(url="attachment://image.png")

                    buf = io.BytesIO()
                    thumbnail["im"].save(buf, format="PNG")
                    buf.seek(0)

                    file = File(buf, "image.png")

                # Send
                await msg.channel.send(embed=embed, file=file)  # type: ignore

            # Notify error
            if has_fail:
                await msg.add_reaction("❌")
