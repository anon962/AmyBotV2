import io
from pathlib import Path
from typing import Any, Callable, TypeAlias

import aiohttp
import PIL
import tomlkit
from PIL import Image


def compose_1arg_fns(*fns):
    def compose(f1, f2):
        return lambda x: f1(f2(x))

    wrapped = lambda x: x
    for fn in fns:
        wrapped = compose(fn, wrapped)
    return wrapped


def load_toml(fp: Path | str):
    if isinstance(fp, str):
        fp = Path(fp)
    return tomlkit.parse(fp.read_text(encoding="utf-8"))


def dump_toml(data: tomlkit.TOMLDocument, fp: Path | str) -> None:
    if isinstance(fp, str):
        fp = Path(fp)

    with open(fp, "w") as file:
        tomlkit.dump(data, file)


def split_lst(lst: list, condition: Callable[[Any], bool]) -> list[list]:
    result: list[list] = []

    buffer = []
    for x in lst:
        if condition(x):
            result.append(buffer)
            buffer = []
        else:
            buffer.append(x)

    if len(buffer):
        result.append(buffer)

    return result


PILImage: TypeAlias = Image.Image


async def download_image(
    url: str,
    headers: dict[str, str] | None = None,
    chunk_size=8192,
) -> PILImage:
    buffer = bytearray()
    async with aiohttp.ClientSession() as session:
        resp = await session.get(url, headers=headers or dict())
        if resp.status != 200:
            raise ValueError()

        async for chunk in resp.content.iter_chunked(chunk_size):
            buffer += chunk

    try:
        im = Image.open(io.BytesIO(buffer))
    except PIL.UnidentifiedImageError as e:
        raise ValueError() from e

    try:
        im.copy().verify()
    except Exception as e:
        raise ValueError() from e

    return im
