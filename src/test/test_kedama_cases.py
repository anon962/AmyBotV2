from dataclasses import dataclass, field
import dataclasses
from classes.scrapers.kedama_scraper import _StrWithHref
from utils.parse import int_to_price


@dataclass
class Equip:
    id: str = "Eq01"
    id_auction: str = ""
    name: str = "Cup of Water"
    eid: int = 12345678
    key: str = "abcdefghij"
    is_isekai: bool = False
    level: int = 500
    stats: str = '["EDB 100%", "MDB 50%"]'
    price: int | None = 50000
    start_bid: int | None = None
    post_index: int | None = 1
    buyer: str | None = "앤 마이어"
    seller: str | None = "프레이 마이어"

    def print(self, format: str):
        def main():
            [fmt_id, fmt_rest] = format.split("#name")
            id = _StrWithHref(text=interpolate(fmt_id), href=None)
            name = _StrWithHref(
                text=self.name,
                href=f"https://hentaiverse.org/equip/{self.eid}/{self.key}",
            )
            rest = _StrWithHref(text=interpolate(fmt_rest), href=None)
            return [id, name, rest]

        def interpolate(format: str) -> str:
            result = format
            for k, v in self.asdict().items():
                match k:
                    case "stats":
                        v = v[1:-1].replace('"', "")
                    case "price":
                        if v is not None:
                            v = int_to_price(v)
                    case "start_bid":
                        if v is not None:
                            v = int_to_price(v)
                    case _:
                        pass

                result = result.replace("#" + str(k), str(v))
            return result

        return main()

    def asdict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class Mat:
    id: str = "Mat01"
    id_auction: str = ""
    name: str = "Low Quality Soul"
    quantity: int = 50
    unit_price: int | None = 1000
    price: int | None = 50000
    start_bid: int | None = None
    post_index: int | None = 1
    buyer: str | None = "앤 마이어"
    seller: str | None = "프레이 마이어"

    def print(self, format: str):
        text = format
        for k, v in self.asdict().items():
            match k:
                case "stats":
                    v = ", ".join(v)
                case "unit_price":
                    if v is not None:
                        v = int_to_price(v)
                case "price":
                    if v is not None:
                        v = int_to_price(v)
                case "start_bid":
                    if v is not None:
                        v = int_to_price(v)
                case _:
                    pass

            text = text.replace("#" + str(k), str(v))

        return [_StrWithHref(text=text, href=None)]

    def asdict(self) -> dict:
        return dataclasses.asdict(self)


# fmt: off
CASES = dict(
    equips=[
        ('[#id] #name (Lv.#level, #stats) (seller: #seller) #buyer #price ##post_index', Equip()), # buyer
        ('[#id] #name (Lv.#level, #stats) (seller: #seller) start:#start_bid #buyer #price ##post_index', Equip(start_bid=5_500_000)), # start bid
        ('[#id] #name (Lv.#level, #stats) (seller: #seller)', Equip(buyer=None, price=None, post_index=None)), # no buyer
        ('[#id] #name (Lv.#level) (seller: #seller) #buyer #price ##post_index', Equip(stats="[]")), # no stats
        ('[#id]#name(Lv.#level, #stats)(seller: #seller) #buyer #price ##post_index', Equip()), # no space
        ('[#id] #name (Lv.#level) (#stats) (seller: #seller) #buyer #price ##post_index', Equip()), # separate stats
        ('[#id] #name (Lv.#level, #stats) (seller: #seller) #buyer 500k ##post_index', Equip(price=500_000)), # thousands
        ('[#id] #name (Lv.#level, #stats) (seller: #seller) #buyer 11.5m ##post_index', Equip(price=11_500_000)), # millions
    ],
    mats=[
        ('[#id] #quantityx #name (seller: #seller) #buyer #price ##post_index', Mat()), # buyer
        ('[#id] #quantityx #name (seller: #seller) start:#start_bid #buyer #price ##post_index', Mat(start_bid=5_500_000)), # start bid
        ('[#id] #quantityx #name (seller: #seller)', Mat(buyer=None, price=None, post_index=None, unit_price=None)), # no buyer
        ('[#id]#quantityx#name(seller:#seller) #buyer #price ##post_index', Mat()), # no space
        ('[#id] #quantityx #name (seller: #seller) #buyer 500k ##post_index', Mat(quantity=50, price=500_000, unit_price=10_000)), # thousands
        ('[#id] #quantityx #name (seller: #seller) #buyer 11.5m ##post_index', Mat(quantity=115, price=11_500_000, unit_price=100_000)), # millions
    ]
)
