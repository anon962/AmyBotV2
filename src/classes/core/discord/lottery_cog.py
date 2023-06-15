from dataclasses import dataclass
import json
import re

from discord.ext import commands
from discord.ext.commands import Context
from datetime import datetime

from classes.core import discord
from classes.core.discord.types import _Lottery as types
from classes.core.discord.checks import check_perms
from classes.core.discord.discord_watchers import (
    DeleteWatcher,
    EditWatcher,
    MoreWatcher,
)
from classes.core.discord.keywords import YearKey
from classes.core.discord.table import Col, Table
from utils.discord import alias_by_prefix, paginate
from utils.http import do_get


@dataclass
class LotteryCog(commands.Cog):
    bot: "discord.AmyBot"

    @commands.command(
        name="litem",
        aliases=alias_by_prefix("litem", starting_at=3),
        extras=dict(id="litem"),
    )
    @commands.check(check_perms("lit"))
    async def text_lottery_item(self, ctx: Context, *, msg: str):
        # Parse
        params: types.FetchParams = dict()  # type: ignore
        rem = msg

        rem, raw = YearKey.extract(rem)
        if raw is not None:
            params["min_date"] = YearKey.convert(raw)

        # Generate table
        params["name"] = rem.strip()
        pages = await self._lottery_item(params)

        if ctx.guild:
            [pages_send, pages_save] = [pages[:3], pages[3:]]
        else:
            [pages_send, pages_save] = [pages[:15], pages[15:]]

        # Send some of the response
        responses = []
        for pg in pages_send:
            resp = await ctx.send(pg)
            responses.append(resp.id)

        # Save the rest for later
        if pages_save:
            resp = await ctx.send(
                f"{len(pages_save)} pages omitted. Use !more to see the rest."
            )
            responses.append(resp.id)

            self.bot.watcher_cog.register(
                await MoreWatcher(ctx.channel.id, self.bot, pages_save).__ainit__()
            )

        self.bot.watcher_cog.register(
            await DeleteWatcher(
                ctx.message.id, responses, ctx.channel.id, self.bot
            ).__ainit__()
        )
        self.bot.watcher_cog.register(
            await EditWatcher(
                ctx.message.id, responses, ctx.channel.id, self.bot
            ).__ainit__()
        )

    async def _lottery_item(self, params: types.FetchParams):
        # Fetch data
        ep = self.bot.api_url / "lottery" / "search"

        fragments = re.sub(r"\s", ",", params["name"].strip())  # type: ignore
        ep %= dict(equip=fragments)

        if params.get("min_date"):
            ep %= dict(min_date=str(params.get("min_date")))

        data = await do_get(ep, content_type="json")
        if len(data) == 0:
            msg = "No data found.\n```yaml\nSearch parameters:"
            debug = params.copy()
            debug["equip_name"] = params["name"]  # type: ignore
            del debug["name"]

            for k, v in debug.items():
                msg += f"\n    {k}: {v}"
            msg += "```"

            pages = paginate(msg)
            return pages
        data.sort(key=lambda x: x["date"], reverse=True)

        # Create table
        tbl = Table()

        prize = [x["prizes"][0][0] for x in data]
        prize_col = Col(header="Grand Prize", stringify=_fmt_name)
        tbl.add_col(prize_col, prize)

        ticket = [x["tickets"] for x in data]
        ticket_col = Col(header="Tickets", stringify=_fmt_tickets, align="right")
        tbl.add_col(ticket_col, ticket)

        winner = [x["prizes"][0][1] for x in data]
        winner_col = Col(header="Winner")
        tbl.add_col(winner_col, winner)

        date = [(x["date"], str(x["lottery"]["id"])) for x in data]
        date_col = Col("Lottery Date", stringify=lambda x: _fmt_date(*x))
        tbl.add_col(date_col, date)

        # Remove padding at edges
        tbl.cols[0].padding_left = 0
        tbl.cols[-1].padding_right = 0

        # Print
        msg = tbl.print()
        msg = f"```css\n{msg}\n```"
        pages = paginate(msg)
        return pages

    @commands.command(
        name="lwinner",
        aliases=alias_by_prefix("lwinner", starting_at=3),
        extras=dict(id="lwinner"),
    )
    @commands.check(check_perms("lwin"))
    async def text_lottery_win(self, ctx: Context, *, msg: str):
        # Parse
        params: types.FetchParams = dict()  # type: ignore
        rem = msg

        rem, raw = YearKey.extract(rem)
        if raw is not None:
            params["min_date"] = YearKey.convert(raw)

        # Generate table
        params["name"] = rem.strip()
        pages = await self._lottery_win(params)

        if ctx.guild:
            [pages_send, pages_save] = [pages[:3], pages[3:]]
        else:
            [pages_send, pages_save] = [pages[:15], pages[15:]]

        # Send some of the response
        responses = []
        for pg in pages_send:
            resp = await ctx.send(pg)
            responses.append(resp.id)

        # Save the rest for later
        if pages_save:
            resp = await ctx.send(
                f"{len(pages_save)} pages omitted. Use !more to see the rest."
            )
            responses.append(resp.id)

            self.bot.watcher_cog.register(
                await MoreWatcher(ctx.channel.id, self.bot, pages_save).__ainit__()
            )

        self.bot.watcher_cog.register(
            await DeleteWatcher(
                ctx.message.id, responses, ctx.channel.id, self.bot
            ).__ainit__()
        )
        self.bot.watcher_cog.register(
            await EditWatcher(
                ctx.message.id, responses, ctx.channel.id, self.bot
            ).__ainit__()
        )

    async def _lottery_win(self, params: types.FetchParams):
        async def main():
            # Fetch data
            ep = self.bot.api_url / "lottery" / "search"
            ep %= dict(user=params["name"])  # type: ignore
            if params.get("min_date"):
                ep %= dict(min_date=str(params.get("min_date")))
            data = await do_get(ep, content_type="json")

            if len(data) == 0:
                msg = "No data found.\n```yaml\nSearch parameters:"
                debug = params.copy()
                debug["user"] = params["name"]  # type: ignore
                del debug["name"]

                for k, v in debug.items():
                    msg += f"\n    {k}: {v}"
                msg += "```"

                pages = paginate(msg)
                return pages
            data.sort(key=lambda x: x["date"], reverse=True)

            # Extract username
            for item, winner in data[0]["prizes"]:
                winner = winner or ""
                if winner.lower() == params["name"].lower():  # type: ignore
                    user = winner
                    break
            else:
                raise Exception(
                    f"{params.get('name')} did not win any prizes in lottery {data[0]}"
                )

            # Print
            item_tbl = create_item_table(data, user).print()
            stats_tbl = create_stats_table(data, user).print()
            msg = f"```css\n@{user}\n\n{stats_tbl}\n\n{item_tbl}\n```"
            pages = paginate(msg)
            return pages

        def create_stats_table(data: list[dict], user: str):
            # Tally winnings
            stats = {
                "Equips": dict(count=0, wins=0),
                "Core Wins": dict(count=0, wins=0),
                "Chaos Tokens": dict(count=0, wins=0),
                "GLTs": dict(count=0, wins=0),
                "Candies": dict(count=0, wins=0),
            }

            # Keys from the dict above but matching the lottery prize order
            stat_keys = [
                "Equips",
                "Core Wins",
                "GLTs",
                "Candies",
                "Chaos Tokens",
                "Chaos Tokens",
            ]

            for lottery in data:
                for idx, (item, winner) in enumerate(lottery["prizes"]):
                    winner = winner or ""
                    if winner == user:
                        stats[stat_keys[idx]]["wins"] += 1

                        if idx in [0, 1]:
                            stats[stat_keys[idx]]["count"] += 1
                        else:
                            [count, name] = item
                            stats[stat_keys[idx]]["count"] += count

                        break
                else:
                    raise Exception(
                        f"User {user} did not win any prizes in lottery {lottery}"
                    )

            # Crate table
            tbl = Table()

            cats = list(stats.keys())
            cats_col = Col(header="Category")
            tbl.add_col(cats_col, cats)

            count = [v["count"] for v in stats.values()]
            count_col = Col(header="Count")
            tbl.add_col(count_col, count)

            wins = [v["wins"] for v in stats.values()]
            wins_col = Col(header="Wins")
            tbl.add_col(wins_col, wins)

            tbl.cols[0].padding_left = 0
            tbl.cols[-1].padding_right = 0

            return tbl

        def create_item_table(data: list[dict], user: str):
            tbl = Table()

            prize_col = Col(header="Prize", stringify=lambda d: fmt_prize(d, user))
            tbl.add_col(prize_col, data)

            grand_prize_col = Col(
                header="Grand Prize", stringify=lambda d: fmt_grand_prize(d, user)
            )
            tbl.add_col(grand_prize_col, data)

            ticket = [x["tickets"] for x in data]
            ticket_col = Col(header="Tickets", stringify=_fmt_tickets, align="right")
            tbl.add_col(ticket_col, ticket)

            date = [(x["date"], str(x["lottery"]["id"])) for x in data]
            date_col = Col("Lottery Date", stringify=lambda x: _fmt_date(*x))
            tbl.add_col(date_col, date)

            tbl.cols[0].padding_left = 0
            tbl.cols[-1].padding_right = 0

            return tbl

        def fmt_prize(lottery: dict, user: str):
            prizes = lottery["prizes"]
            if prizes[0][1] == user:  # type: ignore
                return _fmt_name(prizes[0][0])
            else:
                for prize in prizes[1:]:
                    winner = prize[1] or ""
                    if winner == user:  # type: ignore
                        return _fmt_name(prize[0])
                else:
                    raise Exception(
                        f"User {user} did not win any prizes in lottery {lottery}"
                    )

        def fmt_grand_prize(lottery: dict, user: str):
            if lottery["prizes"][0][1] == user:  # type: ignore
                return "-"
            else:
                return lottery["prizes"][0][0] or "??????????????????????"

        return await main()


def _fmt_date(ts, title) -> str:
    title_str = "#" + title[:4]
    ts_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    return f"{ts_str} / {title_str}"


def _fmt_tickets(val: int) -> str:
    rounded = round(val / 1000)
    return f"{rounded}k"


def _fmt_name(val: str | list | None) -> str:
    if val:
        if isinstance(val, list):
            val = " ".join(str(x) for x in val)
        return val.replace("Peerless ", "")
    else:
        return "??????????????????????"
