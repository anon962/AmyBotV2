from dataclasses import dataclass, field
from typing import Optional

from classes.core import discord
from classes.core.discord import discord_watchers
from config import logger

from discord import (
    Message,
    RawMessageDeleteEvent,
    RawMessageUpdateEvent,
    RawReactionActionEvent,
)
from discord.ext import commands

logger = logger.bind(tags=["discord_bot"])


@dataclass
class WatcherCog(commands.Cog):
    """Watch for changes to messages that triggered a command

    For example, delete the command output when the trigger is deleted
    """

    bot: "discord.AmyBot"

    watchers: list["discord_watchers.DWatcher"] = field(default_factory=list)

    def register(self, w: "discord_watchers.DWatcher") -> None:
        self.watchers.append(w)

    def unregister(self, w: "discord_watchers.DWatcher") -> None:
        try:
            self.watchers.remove(w)
        except ValueError:
            logger.warning(f"Tried to remove unregistered watcher: {w}")

    def purge(
        self,
        message: Optional[int] = None,
        user: Optional[int] = None,
        channel: Optional[int] = None,
        guild: Optional[int] = None,
    ) -> None:
        tgts = []

        for w in self.watchers:
            if message and message == w.message:
                tgts.append(w)
                continue
            if user and user == w.user:
                tgts.append(w)
                continue
            if channel and channel == w.channel:
                tgts.append(w)
                continue
            if guild and guild == w.guild:
                tgts.append(w)
                continue

        if len(tgts) == 0:
            logger.warning(f"Purge failed for args {message} {user} {channel} {guild}")
        else:
            for w in tgts:
                self.unregister(w)

    @commands.Cog.listener()
    async def on_message(self, ctx: Message):
        for w in self.watchers:
            if w.filter_by_message(ctx):
                await w.on_create(ctx)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, ctx: RawMessageUpdateEvent):
        for w in self.watchers:
            if w.filter_by_raw_update(ctx):
                await w.on_update(ctx)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, ctx: RawMessageDeleteEvent):
        for w in self.watchers:
            if w.filter_by_raw_delete(ctx):
                await w.on_delete(ctx)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, ctx: RawReactionActionEvent):
        for w in self.watchers:
            if w.filter_by_raw_reaction(ctx):
                await w.on_reaction_add(ctx)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, ctx: RawReactionActionEvent):
        for w in self.watchers:
            if w.filter_by_raw_reaction(ctx):
                await w.on_reaction_remove(ctx)
