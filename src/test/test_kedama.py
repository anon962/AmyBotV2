from classes.scrapers.kedama_scraper import _Post, KedamaScraper
from test.test_kedama_cases import CASES, Equip, Mat


def to_thread(data: list[tuple[str, Equip | Mat]]) -> list[_Post]:
    content = []
    for format, d in data:

        content.append(d.print(format))

    thread = [
        _Post(
            author=KedamaScraper.KEDAMA_IGN,
            author_id=KedamaScraper.KEDAMA_ID,
            time=0,
            post_id=0,
            post_index=0,
            content=content,
            el=None,  # type: ignore
            content_el=None,  # type: ignore
        )
    ]

    return thread


def test_parsing():
    auction_id = "0"

    for format, data in CASES["equips"]:
        thread = to_thread([(format, data)])
        result = KedamaScraper._parse_thread(auction_id, thread)["equips"][0]

        expected = {**data.asdict(), "id_auction": auction_id}
        assert result == expected

    for format, data in CASES["mats"]:
        thread = to_thread([(format, data)])
        result = KedamaScraper._parse_thread(auction_id, thread)["mats"][0]

        expected = {**data.asdict(), "id_auction": auction_id}
        assert result == expected
