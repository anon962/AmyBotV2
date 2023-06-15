from dataclasses import dataclass
from typing import ClassVar

from classes.core import discord as core
from classes.core.discord.watcher_cog import WatcherCog
from config import logger

import discord
from discord import (
    Message,
    RawMessageDeleteEvent,
    RawMessageUpdateEvent,
    RawReactionActionEvent,
)
from discord.ext.commands import Context

logger = logger.bind(tags=["discord_bot"])


@dataclass
class DWatcher:
    """Interface for handling new messages, edits, reactions, etc

    Due to intents, the user info may not be visible, so don't rely on that for filtering
    """

    bot: "core.AmyBot"
    message: int | None = None
    user: int | None = None
    channel: int | None = None
    guild: int | None = None

    cog: "WatcherCog" = None  # type: ignore
    channel_obj: discord.TextChannel | discord.DMChannel | None = None
    guild_obj: discord.Guild | None = None

    _is_initd = False

    def __post_init__(self):
        self.cog = self.bot.get_cog("WatcherCog")  # type: ignore
        assert self.cog is not None

    async def __ainit__(self):
        if self._is_initd:
            logger.warning(f"Already init'd watcher: {self}")
            return self
        self._is_initd = True

        if self.channel is not None and self.channel_obj is None:
            await self.set_channel(self.channel)
        if self.guild is not None and self.guild_obj is None:
            await self.set_guild(self.guild)

        return self

    @classmethod
    def from_ctx(cls, bot: "core.AmyBot", ctx: Context) -> "DWatcher":
        if ctx.guild:
            return cls(
                bot=bot,
                message=ctx.message.id,
                user=ctx.author.id,
                channel=ctx.channel.id,
                guild=ctx.guild.id,
            )
        else:
            return cls(
                bot=bot,
                message=ctx.message.id,
                user=ctx.author.id,
                channel=ctx.channel.id,
            )

    def filter(
        self,
        message: int | None = None,
        user: int | None = None,
        channel: int | None = None,
        guild: int | None = None,
    ) -> bool:
        return all(
            [
                self.message == message or self.message is None,
                self.user == user or self.user is None,
                self.channel == channel or self.channel is None,
                self.guild == guild or self.guild is None,
            ]
        )

    async def on_create(self, ctx: Message) -> None:
        pass

    async def on_update(self, ctx: RawMessageUpdateEvent) -> None:
        pass

    async def on_delete(self, ctx: RawMessageDeleteEvent) -> None:
        pass

    async def on_reaction_add(self, ctx: RawReactionActionEvent) -> None:
        pass

    async def on_reaction_remove(self, ctx: RawReactionActionEvent) -> None:
        pass

    def filter_by_context(self, ctx: Context) -> bool:
        guild = ctx.guild.id if ctx.guild else None
        return self.filter(ctx.message.id, ctx.author.id, ctx.channel.id, guild)

    def filter_by_message(self, ctx: Message) -> bool:
        guild = ctx.guild.id if ctx.guild else None
        return self.filter(ctx.id, ctx.author.id, ctx.channel.id, guild)

    def filter_by_raw_update(self, ctx: RawMessageUpdateEvent) -> bool:
        return self.filter(ctx.message_id, None, ctx.channel_id, ctx.guild_id)

    def filter_by_raw_delete(self, ctx: RawMessageDeleteEvent) -> bool:
        return self.filter(ctx.message_id, None, ctx.channel_id, ctx.guild_id)

    def filter_by_raw_reaction(self, ctx: RawReactionActionEvent) -> bool:
        return self.filter(ctx.message_id, None, ctx.channel_id, ctx.guild_id)

    async def set_channel(self, channel: int) -> None:
        self.channel = channel

        self.channel_obj = await self.bot.fetch_channel(channel)  # type: ignore
        if self.channel_obj is None:
            raise AssertionError(f"Channel not found: {self.channel}")
        assert isinstance(
            self.channel_obj, (discord.TextChannel, discord.DMChannel)
        ), f'Not a TextChannel: {channel} {self.channel_obj.__dict__.get("type")}'

    async def set_guild(self, guild: int) -> None:
        self.guild = guild
        self.guild_obj = self.bot.get_guild(guild)
        if self.guild_obj is None:
            raise AssertionError(f"Guild not found: {self.guild}")

    def __str__(self):
        return f"{self.message} by {self.user} in channel {self.channel} in guild {self.guild}"


class DeleteWatcher(DWatcher):
    def __init__(
        self, trigger: int, responses: list[int], channel: int, bot: "core.AmyBot"
    ) -> None:
        """
        Args:
            trigger: Message from user
            responses: Messages from bot
            channel:
        """

        super().__init__(bot=bot, message=trigger, channel=channel)
        self.responses = responses

    async def on_delete(self, ctx: RawMessageDeleteEvent) -> None:
        logger.debug(
            f"Message {self.message} with {len(self.responses)} responses deleted"
        )

        self.cog.purge(message=self.message)
        for id in self.responses:
            try:
                msg = await self.channel_obj.fetch_message(id)  # type: ignore
                await msg.delete()
            except discord.errors.NotFound:
                logger.info(f"Could not delete message {id} for trigger {self.message}")


class EditWatcher(DWatcher):
    def __init__(
        self, trigger: int, responses: list[int], channel: int, bot: "core.AmyBot"
    ) -> None:
        """
        Args:
            trigger: Message from user
            responses: Messages from bot
            channel:
        """

        super().__init__(bot=bot, message=trigger, channel=channel)
        self.responses = responses

    async def on_update(self, ctx: RawMessageUpdateEvent) -> None:
        logger.debug(
            f"Message {self.message} with {len(self.responses)} responses edited"
        )

        # Delete old responses
        self.cog.purge(message=self.message)
        for id in self.responses:
            try:
                msg = await self.channel_obj.fetch_message(id)  # type: ignore
                await msg.delete()
            except discord.errors.NotFound:
                logger.info(f"Could not delete message {id} for trigger {self.message}")

        # Let a new watcher take over
        self.cog.unregister(self)

        # Trigger command
        msg = await self.channel_obj.fetch_message(self.message)  # type: ignore
        assert msg is not None
        await self.bot.on_message(msg)


class MoreWatcher(DWatcher):
    chunk_size: ClassVar[int] = 4

    def __init__(
        self, channel: int, bot: "core.AmyBot", remaining_pages: list[str]
    ) -> None:
        super().__init__(bot=bot, channel=channel)
        self.remaining_pages = remaining_pages

        for w in self.cog.watchers:
            if isinstance(w, MoreWatcher) and w.channel == self.channel:
                self.cog.unregister(w)

    async def on_create(self, ctx: Message) -> None:
        is_channel = ctx.channel.id == self.channel
        is_trigger = ctx.content.lower().startswith(f"{self.bot.config['prefix']}more")
        if is_channel and is_trigger:
            logger.debug(
                f"Showing {min(self.chunk_size, len(self.remaining_pages))} more pages in {self.channel}"
            )

            pgs = self.remaining_pages[: self.chunk_size]
            for pg in pgs:
                await ctx.channel.send(pg)
                self.remaining_pages.remove(pg)

            if self.remaining_pages:
                await ctx.channel.send(
                    f"{len(self.remaining_pages)} pages remaining. Use !more to see the rest."
                )
            else:
                self.cog.unregister(self)
