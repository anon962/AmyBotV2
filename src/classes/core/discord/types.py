from dataclasses import dataclass
from typing import Optional, TypedDict


class _Equip:
    class FetchParams(TypedDict, total=False):
        name: str
        min_date: float | None
        min_price: int | None
        max_price: int | None
        seller: str | None
        seller_partial: str | None
        buyer: str | None
        buyer_partial: str | None

    @dataclass
    class FormatOptions:
        show_buyer: bool = False
        show_seller: bool = False
        show_equip_link: bool = False
        show_thread_link: bool = False

    class CogAuction(TypedDict):
        time: float
        is_complete: bool
        title: str

    class CogEquip(TypedDict):
        name: str
        eid: int
        key: str
        is_isekai: bool
        level: int | None
        stats: list[str]
        price: int | None
        min_bid: int
        buyer: str | None
        seller: str
        auction: "_Equip.CogAuction"


class _Lottery:
    class FetchParams(TypedDict, total=False):
        name: str
        min_date: float | None
