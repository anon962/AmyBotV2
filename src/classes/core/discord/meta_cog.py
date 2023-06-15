from dataclasses import dataclass
from typing import Optional
import discord

from discord.ext import commands
from discord.ext.commands import Context

from . import amy_bot


@dataclass
class MetaCog(commands.Cog):
    bot: "amy_bot.AmyBot"

    @commands.command(name="enable_slash_commands")
    async def enable_slash_commands(self, ctx: Context, guild_id: Optional[int]):
        guild = ctx.guild
        if guild_id:
            guild = discord.Object(id=guild_id)

        if guild:
            self.bot.tree.copy_global_to(guild=guild)
            await self.bot.tree.sync(guild=guild)
            await ctx.message.add_reaction("👍")

    @commands.command(name="disable_slash_commands")
    async def disable_slash_commands(self, ctx: Context, guild_id: Optional[int]):
        guild = ctx.guild
        if guild_id:
            guild = discord.Object(id=guild_id)

        if guild:
            self.bot.tree.clear_commands(guild=guild)
            await self.bot.tree.sync(guild=guild)
            await ctx.message.add_reaction("👍")
