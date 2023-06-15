import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Union


@dataclass
class JsonCache:
    """
    Easily dump / load a json from file.
        - automatic creation of parent directories
        - customizable default for when data does not exist
    """

    fp: Union[str, Path]
    default: Union[Callable[[], list | dict], list | dict]
    encoding = "utf-8"

    def __post_init__(self):
        if not isinstance(self.fp, Path):
            self.fp = Path(self.fp)

    def load(self):
        try:
            with open(self.fp, encoding=self.encoding) as file:
                result = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            if callable(self.default):
                result = self.default()
            else:
                result = self.default

        return result

    def dump(self, data: Union[list, dict]):
        os.makedirs(self.fp.parent, exist_ok=True)

        with open(self.fp, "w+", encoding=self.encoding) as file:
            json.dump(data, file, indent=2)
