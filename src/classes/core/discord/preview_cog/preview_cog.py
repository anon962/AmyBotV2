from dataclasses import dataclass

from discord import Message
from discord.ext import commands

from classes.core import discord
from classes.core.discord import types as types
from classes.core.discord.discord_watchers import DeleteWatcher, EditWatcher
from classes.core.discord.preview_cog.on_equip_message import (
    extract_links,
    on_equip_message,
)
from config import logger

logger = logger.bind(tags=["discord_bot"])


@dataclass
class PreviewCog(commands.Cog):
    bot: "discord.AmyBot"

    @commands.Cog.listener()
    async def on_message(self, msg: Message):
        links = extract_links(msg.content)
        if not links:
            return

        async with msg.channel.typing():
            equip_previews, has_fail = on_equip_message(links)
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
