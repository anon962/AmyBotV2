from pathlib import Path
from typing import Callable, Optional
from config import logger
from hachiko.hachiko import AIOEventHandler, AIOWatchdog
from watchdog.events import FileCreatedEvent, FileModifiedEvent
import asyncio


class DirectoryWatcher(AIOEventHandler):
    """Warning: Callbacks may be triggered multiple times for a single edit

    https://github.com/gorakhargosh/watchdog/issues/346
    """

    def __init__(
        self,
        dir: str | Path,
        load_file: Callable,
        filter: Optional[Callable[[Path], bool]] = None,
    ):
        super().__init__(loop=asyncio.get_running_loop())

        self.dir = str(dir)
        self.load_file = load_file
        self.filter = filter

    def start(self):
        AIOWatchdog(self.dir, event_handler=self).start()

    async def on_created(self, event: FileCreatedEvent):
        if not self._filter(event.src_path):
            return

        logger.debug(f"File created: {event.src_path}")
        self.load_file(Path(event.src_path))

    async def on_modified(self, event: FileModifiedEvent):
        if not self._filter(event.src_path):
            return

        logger.debug(f"File updated: {event.src_path}")
        self.load_file(Path(event.src_path))

    def _filter(self, src_path: str):
        if self.filter is None:
            return True
        else:
            fp = Path(src_path)
            result = self.filter(fp)
            return result


class FileWatcher(AIOEventHandler):
    """Warning: Callbacks may be triggered multiple times for a single edit

    https://github.com/gorakhargosh/watchdog/issues/346
    """

    def __init__(
        self,
        file: str | Path,
        load_file: Callable,
    ):
        super().__init__(loop=asyncio.get_running_loop())

        self.file = str(file)
        self.load_file = load_file
        self.filter = filter

    def start(self):
        AIOWatchdog(self.file, event_handler=self).start()

    async def on_modified(self, event: FileModifiedEvent):
        if not event.is_directory:
            logger.debug(f"File updated: {event.src_path}")
            self.load_file(Path(event.src_path))
