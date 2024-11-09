from test.stubs import equip_html

from classes.core.server.fetch_equip import parse_equip_html


def test_custom_name():
    html = equip_html.forge_rename_1.html

    data = parse_equip_html(html)

    assert data["name"] == "Legendary Onyx Power Boots of Slaughter"
    assert data["alt_name"] == "IW10 Power Slaughter Boots - J3 F3"


def test_no_custom_name():
    html = equip_html.forge_1.html

    data = parse_equip_html(html)

    assert data["name"] == "Peerless Ethereal Shortsword of Slaughter"
    assert data["alt_name"] == None


def test_no_font():
    html = equip_html.no_font_1.html

    data = parse_equip_html(html)

    assert data["name"] == "magnificent ruby shade boots of the fleet"
    assert data["alt_name"] == None


def test_no_font_with_alt():
    html = equip_html.no_font_rename_1.html

    data = parse_equip_html(html)

    assert data["name"] == "legendary onyx power boots of slaughter"
    assert data["alt_name"] == "iw10 power slaughter boots  j3 f3"
