from test.stubs import equip_html
from test.stubs.equip_html.ranges import TEST_RANGES

from classes.core.server.fetch_equip import infer_equip_stats, parse_equip_html


def test_equip_parsing():
    for case in equip_html.ALL_CASES:
        data = parse_equip_html(case.html)
        assert data == case.data


def test_equip_inference():
    for case in [equip_html.ALL_CASES[5]]:
        data = parse_equip_html(case.html)
        calcs = infer_equip_stats(data, TEST_RANGES)

        assert set(calcs.keys()) == set(case.calculations.keys())

        for cat in calcs["percentiles"]:
            assert set(calcs["percentiles"][cat].keys()) == set(
                case.calculations["percentiles"][cat].keys()
            )

            for stat in calcs["percentiles"][cat]:
                actual = calcs["percentiles"][cat][stat]
                expected = case.calculations["percentiles"][cat][stat]
                diff = abs(actual - expected)
                assert diff <= 0.05, f"{cat} {stat} {actual} {expected}"
