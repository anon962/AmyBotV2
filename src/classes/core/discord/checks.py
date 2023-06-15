from typing import Any, Callable

from classes.core import discord

from discord import Interaction
from discord.ext.commands import Context


def check_perms(command: str) -> Callable[[Context], bool]:
    def check(ctx: Context) -> bool:
        bot: "discord.AmyBot" = ctx.bot

        if ctx.guild is None:
            return bot.perms_service.check(
                command=command,
                guild=0,
                user=ctx.author.id,
            )
        else:
            return bot.perms_service.check(
                command=command,
                guild=ctx.guild.id,
                user=ctx.author.id,
                channel=ctx.channel.id,
            )

    return check


def app_check_perms(command: str) -> Callable[[Interaction], bool]:
    def check(itn: Interaction) -> bool:
        bot: Any = itn._client

        if itn.guild is None:
            return bot.perms_service.check(
                command=command,
                guild=0,
                user=itn.user.id,
            )
        else:
            return bot.perms_service.check(
                command=command,
                guild=itn.guild.id,
                user=itn.user.id,
                channel=itn.channel_id,
            )

    return check
