from test.stubs import equip_html
from test.stubs.equip_html.ranges import TEST_RANGES

from classes.core.server.fetch_equip import parse_equip_html
from classes.core.server.infer_equip_stats import infer_equip_stats


def test_equip_parsing():
    for case in equip_html.ALL_CASES:
        data = parse_equip_html(case.html)
        assert data == case.data


def test_equip_inference():
    for case in equip_html.ALL_CASES:
        data = parse_equip_html(case.html)
        calcs = infer_equip_stats(data, TEST_RANGES)

        assert set(calcs.keys()) == set(case.calculations.keys())

        for cat in calcs["percentiles"]:
            assert set(calcs["percentiles"][cat].keys()) == set(
                case.calculations["percentiles"][cat].keys()
            )

            for stat in calcs["percentiles"][cat]:
                actual_percent = calcs["percentiles"][cat][stat]
                expected_percent = case.calculations["percentiles"][cat][stat]

                if expected_percent == "ignore":
                    continue

                if expected_percent is None:
                    assert actual_percent is None
                else:
                    assert (
                        actual_percent is not None
                    ), f"{cat} {stat} {base_value} {actual_percent} {expected_percent:.1%}"
                    diff_percent = abs(actual_percent - expected_percent)

                    if stat == "Attack Damage" and data["weapon_damage"]:
                        base_value = data["weapon_damage"]["damage"]["base"]
                    else:
                        base_value = data["stats"][cat][stat]["base"]

                    assert (
                        diff_percent <= 0.05
                    ), f"{cat} {stat} {base_value} {actual_percent:.1%} {expected_percent:.1%}"
