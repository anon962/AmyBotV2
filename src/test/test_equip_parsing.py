from test.stubs import equip_html

from classes.core.server.fetch_equip import parse_equip_html


def test_equip_parsing():
    for case in equip_html.ALL_CASES:
        data = parse_equip_html(case.html)
        assert data == case.data
