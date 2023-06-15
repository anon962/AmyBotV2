import traceback

from classes.core.discord.disk_watchers import FileWatcher
from classes.core.discord.equip_cog import EquipCog
from classes.core.discord.lottery_cog import LotteryCog
from classes.core.discord.meta_cog import MetaCog
from classes.core.discord.services.permissions_service import PermissionsService
from classes.core.discord.watcher_cog import WatcherCog
from config import logger, paths
from tomlkit.toml_document import TOMLDocument
from utils.discord import paginate
from utils.misc import dump_toml, load_toml
from yarl import URL

import discord
from discord.ext import commands
from discord.ext.commands import CheckFailure, Context

logger = logger.bind(tags=["discord_bot"])


class AmyBot(commands.Bot):
    secrets: TOMLDocument = None  # type: ignore
    config: TOMLDocument = None  # type: ignore
    api_url: URL

    perms_service: PermissionsService
    watcher_cog: WatcherCog = None  # type: ignore

    def run(self):
        secrets = load_toml(paths.SECRETS_FILE)
        super().run(secrets["DISCORD_KEY"])  # type: ignore

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__("fake_prefix", *args, intents=intents, **kwargs)

    async def on_ready(self):
        self.perms_service = PermissionsService()

        self.init_secrets()
        self.init_config()

        self.watcher_cog = WatcherCog(self)
        await self.add_cog(self.watcher_cog)
        await self.add_cog(EquipCog(self))
        await self.add_cog(LotteryCog(self))
        await self.add_cog(MetaCog(self))  # should be last cog added

        logger.info(f"Logged in as {bot.user}")

    def init_secrets(self):
        """Read and validate secrets file. Also watch for changes."""
        fp = paths.SECRETS_FILE

        def load(*args) -> bool:
            # Read file
            doc = load_toml(fp)
            data = doc.value

            # Quit if invalid
            if not is_valid(data):
                new_fp = fp.with_suffix(fp.suffix + ".invalid")
                logger.exception(
                    f"Invalid secrets file. Renaming {fp} to {new_fp.name}"
                )
                fp.replace(new_fp)

                if self.secrets:
                    logger.info(f"Reverting secrets to previous state: {fp}")
                    dump_toml(self.secrets, fp)

                return False

            # Apply values
            self.secrets = doc
            return True

        def is_valid(data: dict) -> bool:
            try:
                assert isinstance(data.get("DISCORD_KEY"), str)
            except AssertionError:
                return False

            return True

        result = load()
        if result == False:
            raise Exception(f"Invalid secrets file: {fp}")

        FileWatcher(fp, load).start()

    def init_config(self):
        """Read and validate config file. Also watch for changes."""
        fp = paths.DISCORD_CONFIG

        def load(*args) -> bool:
            # Read file
            doc = load_toml(fp)
            data = doc.value

            # Check validity
            if not is_valid(data):
                new_fp = fp.with_suffix(fp.suffix + ".invalid")
                logger.exception(f"Invalid config file. Renaming {fp} to {new_fp.name}")
                fp.replace(new_fp)

                if self.config:
                    logger.info(f"Reverting config to previous state: {fp}")
                    dump_toml(self.config, fp)

                return False

            # Apply values
            self.config = doc
            self.command_prefix = data["prefix"]
            self.api_url = URL(data["api_url"])
            return True

        def is_valid(data: dict) -> bool:
            try:
                assert isinstance(data.get("prefix"), str)
                assert isinstance(data.get("api_url"), str)
            except AssertionError:
                return False

            return True

        result = load()
        if result == False:
            raise Exception(f"Invalid config file: {fp}")

        FileWatcher(fp, load).start()

    ###

    async def on_command_error(self, ctx, error_) -> None:
        if isinstance(error_, CheckFailure):
            return
        elif isinstance(error_, commands.CommandNotFound):
            logger.debug(f"Command not found {error_}")
            return

        # Get real stack trace
        if isinstance(error_, commands.CommandInvokeError):
            error = error_.original
        else:
            error = error_

        # Format response
        msg = (
            "Unexpected error"
            + "\n```py"
            + "\n@ EXCEPTION:\n"
            + "".join(traceback.format_tb(error.__traceback__))
            + "------------\n"
            + f"{error_}\n"
            + "\n@ MESSAGE:"
            + f"\n{ctx.message.content}"
            + "```"
        )
        logger.exception(msg)
        for pg in paginate(msg):
            await ctx.send(pg)


bot = AmyBot()


@bot.before_invoke
async def log(ctx: Context):
    logger.info(
        f"Invoking [{ctx.command}] on [{ctx.message.content}] by [{ctx.author.id}] in channel [{ctx.channel.id}] in guild [{ctx.guild.id if ctx.guild else None}]"
    )


if __name__ == "__main__":
    bot.run()
