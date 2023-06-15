import copy
import re
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any, Callable, Literal, Optional
from unicodedata import name

from classes.core import discord
from classes.core.discord import types as types
from classes.core.discord.checks import app_check_perms, check_perms
from classes.core.discord.discord_watchers import (
    DeleteWatcher,
    EditWatcher,
    MoreWatcher,
)
from classes.core.discord.keywords import (
    BuyerKey,
    LinkKey,
    MaxPriceKey,
    MinPriceKey,
    SellerKey,
    ThreadKey,
    YearKey,
)
from classes.core.discord.table import Col, Table, clip
from config import logger
from utils.discord import alias_by_prefix, extract_quoted, paginate
from utils.http import do_get
from utils.misc import compose_1arg_fns
from utils.parse import create_equip_link, int_to_price
from yarl import URL

from discord import Interaction, app_commands
from discord.ext import commands
from discord.ext.commands import Context

logger = logger.bind(tags=["discord_bot"])


@dataclass
class EquipCog(commands.Cog):
    bot: "discord.AmyBot"

    @app_commands.command(name="equip")
    @app_commands.describe(
        name='Equip name (eg "leg oak heimd")',
        year="Ignore old auctions (eg 22)",
        show_link="Show equip link",
        show_thread="Show auction link",
        min="Minimum price (eg 500k)",
        max="Maximum price (eg 1m)",
        seller="Username of seller",
        buyer="Username of buyer",
    )
    @app_commands.check(app_check_perms("equip"))
    async def app_equip(
        self,
        itn: Interaction,
        name: Optional[str],
        year: Optional[int],
        show_link: Optional[bool],
        show_thread: Optional[bool],
        min: Optional[str],
        max: Optional[str],
        show_seller: Optional[bool],
        seller: Optional[str],
        show_buyer: Optional[bool],
        buyer: Optional[str],
    ):
        """Search auction data for equips"""

        # If input is None, return None. Else apply each function in fns, from left to right
        noop = lambda *fns: lambda x: compose_1arg_fns(*fns)(x) if x is not None else x

        params = types._Equip.FetchParams()

        params["name"] = name or ""
        params["min_date"] = noop(str, YearKey.convert)(year)
        params["min_price"] = noop(MinPriceKey.convert)(min)
        params["max_price"] = noop(MinPriceKey.convert)(max)
        params["seller"] = seller
        params["buyer"] = buyer

        opts = types._Equip.FormatOptions()
        opts.show_equip_link = bool(show_link)
        opts.show_thread_link = bool(show_thread)
        if show_seller or seller:
            opts.show_seller = True
        if show_buyer or buyer:
            opts.show_buyer = True

        logger.debug(f"Invoking app command equip with: {params} {opts}")

        # for pg in await self._equip(params, opts):
        pages = await self._equip(params, opts)
        if len(pages) == 1:
            await itn.response.send_message(pages[0])
        elif len(pages) > 1:
            # Create pages-omitted-warning
            if (rem := len(pages) - 1) == 1:
                trailer = "1 page omitted. Try !equip to see more."
            else:
                trailer = f"{rem} pages omitted. Try !equip to see more."
            if pages[0][-3:] != "```":
                trailer = "\n" + trailer

            # Append
            resp = paginate(pages[0], page_size=2000 - len(trailer))
            resp = resp[0] + trailer

            # Send
            await itn.response.send_message(resp)

    @commands.command(
        name="equip",
        aliases=alias_by_prefix("equip", starting_at=2),
        extras=dict(id="equip"),
    )
    @commands.check(check_perms("equip"))
    async def text_equip(self, ctx: Context, *, msg: str):
        async def main():
            # Get response
            params, opts = parse(msg)
            pages = await self._equip(params, opts)

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

        def parse(
            text: str,
        ) -> tuple[types._Equip.FetchParams, types._Equip.FormatOptions]:
            # Pair dict key with prefix / extractor / converter
            parsers: list[
                tuple[
                    str,
                    str,
                    Callable[[str], tuple[str, str | None]],
                    Callable[[str], Any],
                ]
            ] = [
                ("min_date", YearKey.prefix, YearKey.extract, YearKey.convert),
                ("link", LinkKey.prefix, LinkKey.extract, lambda x: x is not None),
                (
                    "thread",
                    ThreadKey.prefix,
                    ThreadKey.extract,
                    lambda x: x is not None,
                ),
                (
                    "min_price",
                    MinPriceKey.prefix,
                    MinPriceKey.extract,
                    MinPriceKey.convert,
                ),
                (
                    "max_price",
                    MaxPriceKey.prefix,
                    MaxPriceKey.extract,
                    MaxPriceKey.convert,
                ),
                (
                    "seller",
                    SellerKey.prefix,
                    SellerKey.extract,
                    lambda x: x if x else True,
                ),
                (
                    "buyer",
                    BuyerKey.prefix,
                    BuyerKey.extract,
                    lambda x: x if x else True,
                ),
            ]
            rem = text

            # Isolate any quoted sections
            # eg "the quick'brown dog'" becomes ("the ", [("brown dog", "quick")])
            (rem, quoted) = extract_quoted(rem)

            # Extract keywords from remaining
            data = dict()
            for key, _, extract, convert in parsers:
                rem, raw = extract(rem)
                if raw is not None:
                    val = convert(raw)
                    if val is not None:
                        data[key] = val

            # Extract keyword data from quoted sections with a prefix (eg quick"brown dog")
            for q_key, q_val in quoted:
                if q_key is not None:
                    key, convert = next(
                        (key, convert)
                        for (key, prefix, _, convert) in parsers
                        if prefix == q_key
                    )
                    try:
                        val = convert(q_val)
                        if val is not None:
                            data[key] = val
                    except:
                        continue

            # rem should be kw-free now
            # Bring back and quoted sections that did not represent keywords
            for q_key, q_val in quoted:
                if q_key is None:
                    rem += " " + q_val
            data["name"] = rem

            # Split into params and options
            params = data.copy()
            opts = types._Equip.FormatOptions()

            if params.get("link"):
                opts.show_equip_link = True
                del params["link"]
            if params.get("thread"):
                opts.show_thread_link = True
                del params["thread"]
            if params.get("seller"):
                opts.show_seller = True
                if params["seller"] is True:
                    del params["seller"]
            if params.get("buyer"):
                opts.show_buyer = True
                if params["buyer"] is True:
                    del params["buyer"]

            # Return
            return params, opts  # type: ignore

        await main()

    async def _equip(
        self, params: types._Equip.FetchParams, opts: types._Equip.FormatOptions
    ) -> list[str]:
        async def main():
            # Fetch data
            warning_params = None
            params_ = params.copy()
            opts_ = copy.deepcopy(opts)
            items = await _fetch_equips(self.bot.api_url, params_)

            # If no results, allow partial seller
            if len(items) == 0 and params.get("seller"):
                params_["seller_partial"] = params.get("seller")
                del params_["seller"]
                items = await _fetch_equips(self.bot.api_url, params_)
                warning_params = f'Hint: Try using quotes if you are looking for a name containing a space (eg `seller"amy bot"`)'

            # If no results, allow partial buyer
            if len(items) == 0 and params.get("buyer"):
                params_["buyer_partial"] = params.get("buyer")
                del params_["buyer"]
                items = await _fetch_equips(self.bot.api_url, params_)
                warning_params = f'Hint: Try using quotes if you are looking for a name containing a space (eg `buyer"amy bot"`)'

            # Still no results, return error
            if len(items) == 0:
                msg = "No equips found.\n```yaml\nSearch parameters:"
                for k, v in params.items():
                    msg += f"\n    {k}: {v}"
                msg += "```"

                if warning_params:
                    msg += "\n" + warning_params

                pages = paginate(msg)
                return pages

            # If all items are from single buyer or seller, show table of user stats and table of items
            # Else show table each for each item name
            msg = ""
            sellers = list(set(x["seller"] for x in items))
            buyers = list(set(x["buyer"] for x in items))
            if (
                len(sellers) == 1
                and None not in sellers
                or len(buyers) == 1
                and None not in buyers
            ):
                if len(sellers) == 1:
                    user = sellers[0]
                    opts_.show_seller = False
                else:
                    user = buyers[0]
                    opts_.show_buyer = False

                items = sorted(
                    items, key=lambda it: it["auction"]["time"], reverse=True
                )
                sales_table = create_sales_table(items)
                item_table = create_item_table(
                    items,
                    show_name=True,
                    show_buyer=opts_.show_buyer,
                    show_seller=opts_.show_seller,
                )

                if opts_.show_equip_link or opts_.show_thread_link:
                    link_type = "equip" if opts_.show_equip_link else "thread"
                    sales_table_text = sales_table.print()
                    item_table_text = item_table.print(
                        cb=partial(append_link, items=items, type=link_type)
                    )

                    msg = (
                        "```py"
                        + f"\n@ {user}"
                        + f"\n\n{sales_table_text}"
                        + "```"
                        + f"\n{item_table_text}"
                    )
                else:
                    sales_table_text = sales_table.print()
                    item_table_text = item_table.print()

                    msg = (
                        "```py"
                        + f"\n@ {user}"
                        + f"\n\n{sales_table_text}"
                        + f"\n\n{item_table_text}"
                        + "```"
                    )
            else:
                items = sorted(items, key=lambda it: it["price"] or 0, reverse=True)
                groups = group_by_name(items)
                tables = {
                    name: create_item_table(
                        lst,
                        show_buyer=opts_.show_buyer,
                        show_seller=opts_.show_seller,
                    )
                    for name, lst in groups.items()
                }

                if opts_.show_equip_link or opts_.show_thread_link:
                    link_type = "equip" if opts_.show_equip_link else "thread"
                    table_texts = {
                        name: tbl.print(
                            cb=partial(append_link, items=grp, type=link_type)
                        )
                        for grp, (name, tbl) in zip(groups.values(), tables.items())
                    }
                    pieces = [
                        f"**{name}**\n{text}" for name, text in table_texts.items()
                    ]
                    msg = "\n\n".join(pieces)

                    if warning_params:
                        msg += "\n\n" + warning_params
                else:
                    pieces = [
                        f"@ {name}\n{tbl.print()}" for name, tbl in tables.items()
                    ]
                    msg = "\n\n".join(pieces)
                    msg = f"```py\n{msg}```"

                    if warning_params:
                        msg += warning_params

            # Paginate
            pages = paginate(msg)
            return pages

        def group_by_name(
            items: list[types._Equip.CogEquip],
        ) -> dict[str, list[types._Equip.CogEquip]]:
            map = {}
            for item in items:
                map.setdefault(item["name"], []).append(item)
            return map

        def create_item_table(
            items: list[types._Equip.CogEquip],
            show_name=False,
            show_buyer=False,
            show_seller=False,
        ) -> Table:
            tbl = Table()

            # Name col
            if show_name:
                names = [x["name"] for x in items]
                name_col = Col(header="Item")
                tbl.add_col(name_col, names)

            # Price col
            prices = items
            price_col = Col(header="Price", stringify=_fmt_price, align="right")
            tbl.add_col(price_col, prices)

            # User cols
            if show_buyer:
                buyers = [d["buyer"] or "" for d in items]
                buyer_col = Col(header="Buyer")
                tbl.add_col(buyer_col, buyers)
            if show_seller:
                sellers = [d["seller"] or "" for d in items]
                seller_col = Col(header="Seller")
                tbl.add_col(seller_col, sellers)

            # Stats col
            stats = [d["stats"] for d in items]
            stat_col = Col(header="Stats", stringify=_fmt_stats)
            tbl.add_col(stat_col, stats)

            # Level col
            levels = [d["level"] or 0 for d in items]
            level_col = Col(header="Level", align="right")
            tbl.add_col(level_col, levels)

            # Date col
            dates = [(d["auction"]["time"], d["auction"]["title_short"]) for d in items]  # type: ignore
            date_col = Col(header="#Auction / Date", stringify=lambda x: _fmt_date(*x))
            tbl.add_col(date_col, dates)

            # Remove padding at edges
            tbl.cols[0].padding_left = 0
            tbl.cols[-1].padding_right = 0

            return tbl

        def create_sales_table(items: list[types._Equip.CogEquip]):
            """Tally earnings for each equip category (eg 1H, Staff, etc)"""

            # Calculate total sales for each category
            cats = {
                "1H": ["axe", "club", "rapier", "shortsword", "wakizashi"],
                "2H": ["estoc", "longsword", "mace", "katana"],
                "Staff": ["oak", "redwood", "willow", "katalox"],
                "Shield": ["buckler", "kite", "force"],
                "Cloth": ["cotton", "phase"],
                "Light": ["leather", "shade"],
                "Heavy": ["plate", "power"],
                "Other": [],
            }
            counts = {k: 0 for k in cats}
            credits = {k: 0 for k in cats}

            for it in items:
                for cat, aliases in cats.items():
                    if any(alias.lower() in it["name"].lower() for alias in aliases):
                        counts[cat] += 1
                        credits[cat] += it["price"] or 0
                        break
                else:
                    counts["Other"] += 1
                    credits["Other"] += it["price"] or 0

            # Create table
            tbl = Table(draw_col_trailers=True)
            tbl.add_col(
                col=Col(
                    header="Category",
                    trailer=">Total<",
                ),
                cells=list(cats.keys()),
            )
            tbl.add_col(
                col=Col(
                    header="Count",
                    trailer=str(sum(counts.values())),
                    align="right",
                ),
                cells=list(counts.values()),
            )
            tbl.add_col(
                col=Col(
                    header="Credits",
                    trailer=int_to_price(sum(credits.values()), precision=(0, 0, 1)),
                    align="right",
                    stringify=partial(int_to_price, precision=(0, 0, 1)),
                ),
                cells=list(credits.values()),
            )
            tbl.cols[0].padding_left = 0
            tbl.cols[-1].padding_right = 0

            return tbl

        def append_link(
            row_text: str,
            row_type: str,
            idx: int | None,
            items: list[types._Equip.CogEquip],
            type: Literal["equip", "thread"] = "equip",
        ):
            """Append link to table row"""

            if row_type == "BODY":
                item = items[idx]  # type: ignore
                if type == "equip":
                    url = create_equip_link(item["eid"], item["key"], item["is_isekai"])
                else:
                    url = f"https://forums.e-hentai.org/index.php?showtopic={item['auction']['id']}"
                result = f"`{row_text} | `{url}"
            else:
                result = f"`{row_text} | `"
            return result

        return await main()


async def _fetch_equips(
    api_url: URL,
    params: types._Equip.FetchParams,
) -> list[types._Equip.CogEquip]:
    """Hit search endpoints for equip data

    Rearranges keys in the response to satisfy CogEquip
    (because the endpoints return slightly different dtos)
    """

    ep_super = api_url / "super" / "search_equips"
    ep_kedama = api_url / "kedama" / "search_equips"

    # Search for equip that contains all words
    # so order doesn't matter and partial words are okay
    # eg "lege oak heimd" should match "Legendary Oak Staff of Heimdall"
    name_fragments = re.sub(r"\s", ",", params.get("name", "").strip())
    ep_super %= dict(name=name_fragments)
    ep_kedama %= dict(name=name_fragments)

    keys: list[str] = [
        "min_date",
        "min_price",
        "max_price",
        "seller",
        "seller_partial",
        "buyer",
        "buyer_partial",
    ]
    for k in keys:
        if (v := params.get(k)) is not None:
            ep_super %= {k: str(v).strip()}
            ep_kedama %= {k: str(v).strip()}

    # Ignore on-going auctions
    ep_super %= dict(complete="true")

    super_data = await do_get(ep_super, content_type="json")
    kedama_data = await do_get(ep_kedama, content_type="json")

    # Normalize
    for x in super_data:
        x["auction"]["title_short"] = "S" + x["auction"]["title"].zfill(3)
        x["auction"]["time"] = x["auction"]["end_time"]
        del x["auction"]["end_time"]
        x["min_bid"] = x["next_bid"]
        del x["next_bid"]
    for x in kedama_data:
        x["auction"]["title_short"] = "K" + x["auction"]["title_short"].zfill(3)
        x["auction"]["time"] = x["auction"]["start_time"]
        del x["auction"]["start_time"]
        x["min_bid"] = x["start_bid"]
        del x["start_bid"]

    resp = super_data + kedama_data
    return resp


def _fmt_price(item: types._Equip.CogEquip) -> str:
    price = item["price"]
    min_bid = item["min_bid"] or 0

    if price is None or price <= 0:
        min_bid_str = int_to_price(min_bid, precision=(0, 0, 1))
        min_bid_str = f"({min_bid_str})"
        return min_bid_str
    elif price > 0:
        return int_to_price(price, precision=(0, 0, 1))
    else:
        raise Exception("Pylance please...")


def _fmt_stats(stats: list[str]) -> str:
    def value(stat) -> int:
        stat = stat.lower()
        if any(x in stat for x in ["forged"]):
            return 30
        elif any(x in stat for x in ["edb", "adb", "mdb"]):
            return 20
        elif any(x in stat for x in ["prof", "blk", "iw"]):
            return 10
        else:
            return 1

    sorted_ = sorted(stats, key=lambda st: value(st), reverse=True)

    simplified = [
        re.sub(r".* ((?:EDB|Prof))", r"\1", st, flags=re.IGNORECASE) for st in sorted_
    ]
    text = ", ".join(simplified[:3])
    clipped = clip(text, 18, "..")
    return clipped


def _fmt_date(ts, title):
    title_str = "#" + title[:4]
    ts_str = datetime.fromtimestamp(ts).strftime("%m-%Y")
    return f"{title_str} / {ts_str}"
