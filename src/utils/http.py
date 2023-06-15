from typing import Any, Literal

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from yarl import URL

from config import logger


async def do_get(
    url: str | URL,
    session: ClientSession | None = None,
    content_type: Literal["html", "text", "json"] = "html",
) -> Any:
    """Perform a GET

    Args:
        url:
        session: For accumulating cookies
        content_type: Whether to return a BeautifulSoup instance, str, or list / dict

    Raises:
        Exception:
        ValueError:
    """
    session_ = session or create_session()

    logger.info(f"GET {url}")
    resp = await session_.get(url)
    if resp.status != 200:
        raise Exception(resp.status)

    match content_type:
        case "html":
            result = await resp.text(encoding="utf-8")
            result = BeautifulSoup(result, "lxml")
        case "text":
            result = await resp.text(encoding="utf-8")
        case "json":
            result = await resp.json(encoding="utf-8")
        case default:
            raise Exception(content_type)

    if session is None:
        await session_.close()

    return result


async def do_post(
    url: URL,
    data: Any = None,
    session: ClientSession | None = None,
    content_type: Literal["html", "text", "json"] = "html",
) -> Any:
    session_ = session or create_session()

    logger.info(f"POST {url}")
    resp = await session_.post(url, data=data)
    if resp.status != 200:
        raise Exception(resp.status)

    match content_type:
        case "html":
            result = await resp.text(encoding="utf-8")
            result = BeautifulSoup(result, "lxml")
        case "text":
            result = await resp.text(encoding="utf-8")
        case "json":
            result = await resp.json(encoding="utf-8")
        case default:
            raise Exception(content_type)

    if session is None:
        await session_.close()

    return result


def create_session():
    session = ClientSession(
        headers={
            # https://github.com/aio-libs/aiohttp/issues/3904#issuecomment-632661245
            "Connection": "keep-alive"
        }
    )
    return session
