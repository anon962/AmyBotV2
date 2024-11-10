# https://hentaiverse.org/equip/137788574/f882d02b92
# forged, iw'd, soulbound

data = dict(
    name="Legendary Ethereal Rapier of Slaughter",
    alt_name="IW10 Ethereal Rapier DW - B4 F3 O2 Cold",
    category="One-handed Weapon",
    level="Soulbound",
    condition=dict(
        current=349,
        max=383,
    ),
    potency=dict(
        tier=10,
        current_xp=None,
        max_xp=None,
    ),
    weapon_damage=dict(
        damage=dict(
            type="Void",
            value=2275,
            base=73.37,
        ),
        strikes=[
            "Cold",
            "Void",
        ],
        status_effects=[
            "Penetrated Armor : 21.7% chance - 7 turns",
        ],
    ),
    stats={
        "misc": {
            "Attack Accuracy": dict(value=25.74, base=23.4),
            "Attack Crit Chance": dict(value=8.76, base=7.01),
            "Attack Crit Damage": dict(value=6.00, base=6.0),
            "Counter-Parry": dict(value=8.00, base=8.0),
            "Parry Chance": dict(value=29.43, base=23.54),
        },
        "Primary Attributes": {
            "Strength": dict(value=73.29, base=4.89),
            "Dexterity": dict(value=108.80, base=7.25),
            "Agility": dict(value=68.21, base=4.55),
        },
    },
    upgrades={
        "Physical Damage": 25,
        "Physical Hit Chance": 5,
        "Physical Crit Chance": 40,
        "Parry Chance": 50,
        "Strength Bonus": 20,
        "Dexterity Bonus": 25,
        "Agility Bonus": 13,
    },
    enchants={
        "Cold Strike": 1,
        "Butcher": 4,
        "Fatality": 3,
        "Overpower": 2,
    },
    owner=dict(
        name="Scremaz",
        uid=11328,
    ),
)

calculations = dict(
    percentiles={
        "weapon_damage": {
            "Attack Damage": 0.90,
        },
        "misc": {
            "Attack Accuracy": 0.92,
            # Diff between lpr and wiki in iw-related constants
            # "Attack Crit Chance": 0.95,
            "Attack Crit Chance": "ignore",
            "Attack Crit Damage": None,
            "Counter-Parry": None,
            "Parry Chance": 0.49,
        },
        "Primary Attributes": {
            "Strength": 0.97,
            "Dexterity": 0.46,
            "Agility": 0.75,
        },
    }
)


html = """
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en"><head>
	<meta http-equiv="Content-type" content="text/html; charset=UTF-8">
	<title>The HentaiVerse</title>
	<link rel="stylesheet" type="text/css" href="/z/090c/hvg.css">
	<link rel="stylesheet" type="text/css" href="/z/090c/hvo.css">
	<meta name="robots" content="noindex,nofollow">
	<link rel="icon" type="image/png" href="/y/favicon.png">
</head>
<body>
<script type="text/javascript" src="/z/090c/hvc.js"></script>
<div id="showequip">
	<div><div style="height:36px"><div style="height:15px"><div class="fc4 fac fcb"><div>IW10 Ethereal Rapier DW - B4 F3 O2</div></div></div><div style="height:3px"></div><div style="height:15px"><div class="fc4 fac fcb"><div>Cold</div></div></div></div></div>
	<div><div style="height:16px"><div style="height:13px"><div class="fc2 fac fcb"><div>Legendary Ethereal Rapier of Slaughter</div></div></div></div></div>
	
<div id="equip_extended">
	<div class="eq es"><div>One-handed Weapon &nbsp; &nbsp; &nbsp; &nbsp; <span>Soulbound</span></div><div>Condition: 349 / 383 (92%) &nbsp; &nbsp; Potency Tier: 10 (MAX)</div><div><span>Penetrated Armor</span>: <span>21.7%</span> chance - <span>7</span> turns</div><div title="Base: 73.37">+<span>2275 Void Damage</span></div><div><span>Cold Strike</span> + <span>Void Strike</span></div><div class="ex"><div title="Base: 23.4"><div>Attack Accuracy</div><div>+<span>25.74</span></div><div> %</div></div><div title="Base: 7.01"><div>Attack Crit Chance</div><div>+<span>8.76</span></div><div> %</div></div><div title="Base: 6"><div>Attack Crit Damage</div><div>+<span>6.00</span></div><div> %</div></div><div title="Base: 8"><div>Counter-Parry</div><div>+<span>8.00</span></div><div> %</div></div><div title="Base: 23.54"><div>Parry Chance</div><div>+<span>29.43</span></div><div> %</div></div><div></div></div><div class="ep"><div>Primary Attributes</div><div title="Base: 4.89">Strength +<span>73.29</span></div><div title="Base: 7.25">Dexterity +<span>108.80</span></div><div title="Base: 4.55">Agility +<span>68.21</span></div></div></div>
	<div>
		<div>Upgrades and Enchantments</div>
		<span id="eu"><span>Physical Damage Lv.25</span> &nbsp; <span>Physical Hit Chance Lv.5</span> &nbsp; <span>Physical Crit Chance Lv.40</span> &nbsp; <span>Parry Chance Lv.50</span> &nbsp; <span>Strength Bonus Lv.20</span> &nbsp; <span>Dexterity Bonus Lv.25</span> &nbsp; <span>Agility Bonus Lv.13</span></span> &nbsp; <span id="ep"><span>Cold Strike</span> &nbsp; <span>Butcher Lv.4</span> &nbsp; <span>Fatality Lv.3</span> &nbsp; <span>Overpower Lv.2</span></span>
	</div>
</div>
	<div>Current Owner: <a target="_forums" href="https://forums.e-hentai.org/index.php?showuser=11328">Scremaz</a></div>
</div>


</body></html>
"""
