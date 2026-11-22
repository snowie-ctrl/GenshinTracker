"""Fake data for demos and end-to-end tests: python -m app.devseed --root PATH"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from app.config import Paths
from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import (CharacterGoal, GameBanner, GameCharacter, GameDomain, GameMaterial, GameMeta, GameWeapon,
                           HoyolabSnapshot, Tag, Team, TeamMember, TeamTag)
from app.planner.requests import snapshot
from app.sync.hoyolab import ArtifactInfo, DetailEntry, GapResult, MaterialAmount, NotesInfo, RosterEntry, WeaponInfo
from app.sync.persist import save_details, save_gaps, save_notes, save_roster
from app.timeutil import iso, utcnow
from app.wishes.merge import merge
from app.wishes.types import IncomingWish, server_local_now

# (id, name, slug, rarity, element, weapon, icon)
CHARACTERS = [
    (10000032, "Bennett", "bennett", 4, "Pyro", "Sword", "UI_AvatarIcon_Bennett"),
    (10000089, "Furina", "furina", 5, "Hydro", "Sword", "UI_AvatarIcon_Furina"),
    (10000023, "Xiangling", "xiangling", 4, "Pyro", "Polearm", "UI_AvatarIcon_Xiangling"),
    (10000073, "Nahida", "nahida", 5, "Dendro", "Catalyst", "UI_AvatarIcon_Nahida"),
    (10000047, "Kaedehara Kazuha", "kazuha", 5, "Anemo", "Sword", "UI_AvatarIcon_Kazuha"),
    (10000087, "Neuvillette", "neuvillette", 5, "Hydro", "Catalyst", "UI_AvatarIcon_Neuvillette"),
    (10000052, "Raiden Shogun", "raiden-shogun", 5, "Electro", "Polearm", "UI_AvatarIcon_Shougun"),
    (10000025, "Xingqiu", "xingqiu", 4, "Hydro", "Sword", "UI_AvatarIcon_Xingqiu"),
]
OWNED = {10000032: (80, (6, 8, 8)), 10000089: (90, (9, 9, 9)), 10000023: (80, (6, 6, 6)), 10000073: (90, (8, 8, 8))}
GOALS = {10000032: "build", 10000089: "build", 10000047: "want", 10000087: "build"}
WEAPON = WeaponInfo("Favonius Sword", "https://enka.network/ui/UI_EquipIcon_Sword_Zephyrus.png", 4, 90, 3, 11401)

# (id, name, category, rarity, craft_from, yatta_type, sources)
MATERIALS = [
    (202, "Mora", "exp", 3, None, "commonCurrency", []),
    (104003, "Hero's Wit", "exp", 4, None, "characterEXPMaterial", []),
    (104111, "Agnidus Agate Sliver", "ascension", 2, None, "characterAscensionMaterial", []),
    (104112, "Agnidus Agate Fragment", "ascension", 3, 104111, "characterAscensionMaterial", []),
    (100055, "Small Lamp Grass", "specialty", 1, None, "localSpecialtyMondstadt",
     [{"kind": "region", "name": "Mondstadt", "days": []}]),
    (104301, "Teachings of Freedom", "talent", 2, None, "characterTalentMaterial", []),
    (104302, "Guide to Freedom", "talent", 3, 104301, "characterTalentMaterial", []),
    (104303, "Philosophies of Freedom", "talent", 4, 104302, "characterTalentMaterial", []),
    (113003, "Dvalin's Plume", "weekly", 5, None, "characterLevelUpMaterial",
     [{"kind": "weekly_boss", "name": "Stormterror", "days": []}]),
    (104319, "Crown of Insight", "special", 5, None, "characterTalentMaterial", []),
]
FREEDOM_SOURCE = {"kind": "domain", "name": "Domain of Mastery: Forsaken Rift", "days": [0, 1, 2, 3, 4, 5, 6]}
WEAPONS = [(11401, "Favonius Sword", "UI_EquipIcon_Sword_Zephyrus", 4, "Sword"),
           (11509, "Mistsplitter Reforged", "UI_EquipIcon_Sword_Narukami", 5, "Sword"),
           (13407, "Favonius Lance", "UI_EquipIcon_Pole_Zephyrus", 4, "Polearm"),
           (14504, "A Thousand Floating Dreams", "UI_EquipIcon_Catalyst_Ayus", 5, "Catalyst"),
           (15301, "Slingshot", "UI_EquipIcon_Bow_Sling", 3, "Bow")]


def _amount(mid, need, short):
    name = next(m[1] for m in MATERIALS if m[0] == mid)
    return MaterialAmount(mid, name, "", 3, need, short)


def demo_wishes(start_local: str) -> list[IncomingWish]:
    """Pulls one minute apart from start_local; ids increase with time."""
    t0 = datetime.strptime(start_local, "%Y-%m-%d %H:%M:%S") + timedelta(hours=1)
    plans = [
        ("character", "301", 30, {10: ("Bennett", 4, "character"), 20: ("Neuvillette", 5, "character"),
                                  28: ("Furina", 5, "character")}),
        ("weapon", "302", 12, {5: ("Favonius Sword", 4, "weapon")}),
        ("standard", "200", 60, {30: ("Xingqiu", 4, "character"), 45: ("Kaedehara Kazuha", 5, "character")}),
    ]
    out, n = [], 0
    for pool, gacha_type, count, special in plans:
        for i in range(1, count + 1):
            name, rarity, item_type = special.get(i, ("Slingshot", 3, "weapon"))
            time = (t0 + timedelta(minutes=n)).strftime("%Y-%m-%d %H:%M:%S")
            out.append(IncomingWish(id=str(1700000000000000000 + n), pool=pool, gacha_type=gacha_type, time=time,
                                    name=name, item_type=item_type, rarity=rarity))
            n += 1
    return out


def seed(root: Path) -> None:
    paths = Paths(root)
    paths.ensure()
    if paths.db_file.exists():
        paths.db_file.unlink()
    engine = make_engine(paths.db_file)
    migrate(engine)
    sf = make_session_factory(engine)
    now = utcnow()
    with sf.begin() as s:
        for cid, name, slug, rarity, element, weapon, icon in CHARACTERS:
            s.add(GameCharacter(id=cid, name=name, slug=slug, rarity=rarity, element=element,
                                weapon_type=weapon, region=None, icon=icon,
                                splash=icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_"),
                                release_at=datetime(2020, 9, 28)))
        s.merge(GameMeta(key="characters_fetched_at", value=iso(now)))
        s.flush()
        names = {c[0]: c[1] for c in CHARACTERS}
        save_roster(s, [RosterEntry(cid, cid, names[cid], None, lvl, 1, 10, WEAPON)
                        for cid, (lvl, _t) in OWNED.items()], now)
        art = ArtifactInfo(1, "Noblesse Oblige", 5, 20, "HP 4780", ["CRIT Rate 3.9%", "ER 11.0%"],
                           "https://enka.network/ui/UI_RelicIcon_15007_4.png")
        save_details(s, [DetailEntry(cid, *t, WEAPON, [art], [{"name": "Max HP", "value": "20000"}])
                         for cid, (_l, t) in OWNED.items()])
        save_notes(s, NotesInfo(120, 200, 80 * 8 * 60, 3, 4, 900, 2400, []), now)
        for cid, goal in GOALS.items():
            build = goal == "build"
            s.add(CharacterGoal(character_id=cid, goal=goal, target_level=90 if build else None,
                                target_normal=8 if build else None, target_skill=8 if build else None,
                                target_burst=8 if build else None,
                                target_weapon_level=90 if build else None, updated_at=now))
        for order, (mid, name, cat, rarity, craft, ytype, sources) in enumerate(MATERIALS):
            src = [FREEDOM_SOURCE] if cat == "talent" else sources
            s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=rarity, yatta_type=ytype,
                               category=cat,
                               family=104301 if cat == "talent" else (104111 if mid in (104111, 104112) else mid),
                               craft_from=craft, sources=src, sort_order=order, detail_fetched=True))
        s.add(GameDomain(id=4213, name="Domain of Mastery: Forsaken Rift", kind="talent", city=1,
                         weekdays=[0, 1, 2, 3, 4, 5, 6], material_ids=[104303, 104302, 104301]))
        for wid, name, icon, rarity, wtype in WEAPONS:
            s.add(GameWeapon(id=wid, name=name, icon=icon, rarity=rarity, weapon_type=wtype))
        s.merge(GameMeta(key="materials_fetched_at", value=iso(now)))
        s.flush()
        result = GapResult(
            per_character={
                10000032: [_amount(104302, 9, 4), _amount(104303, 6, 0), _amount(113003, 2, 2), _amount(104003, 20, 0)],
                10000089: [_amount(104302, 6, 4), _amount(104319, 1, 1)],
            },
            total=[_amount(104302, 15, 7), _amount(104303, 6, 0), _amount(113003, 2, 2), _amount(104003, 20, 0),
                   _amount(104319, 1, 1)],
            spare=[_amount(104301, 9, 0)],
        )
        save_gaps(s, result, snapshot(s), [], now)
    with sf.begin() as s:
        local = datetime.strptime(server_local_now(now, 8), "%Y-%m-%d %H:%M:%S")
        start = (local - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        end = (local + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        banners = [
            ("character", "Tide of Furina", "Furina", start, end, [10000089], [10000032, 10000025]),
            ("weapon", "Epitome Invocation", "Mistsplitter", start, end, [11509, 14504], [11401, 13407]),
            ("standard", "Wanderlust Invocation", "Wanderlust Invocation", "2000-01-01 00:00:00",
             "2200-01-01 00:00:00", [], []),
        ]
        for pool, name, short, b_start, b_end, f5, f4 in banners:
            s.add(GameBanner(key=f"{pool}|{b_start}|0", pool=pool, name=name, short_name=short, start=b_start,
                             end=b_end, timezone_dependent=False, timezone_dependent_end=False, order=0,
                             featured_5=f5, featured_4=f4, version="9.9"))
        s.merge(GameMeta(key="banners_fetched_at", value=iso(now)))
        s.flush()
        merge(s, demo_wishes(start), "game", now)
    with sf.begin() as s:
        ids = {c[2]: c[0] for c in CHARACTERS}             # slug -> id
        s.add(Tag(id=2, name="abyss", name_key="abyss", color="red", builtin=False))
        teams = [
            (1, "Abyss Furina", "Demo: Build + abyss.", [("furina", "on-field"), ("bennett", "battery"),
                                                         ("xingqiu", "off-field hydro")], [1, 2]),
            (2, "Archons only", "", [("furina", ""), ("nahida", ""), ("raiden-shogun", "")], []),
        ]
        for order, (tid, name, notes, members, tags) in enumerate(teams):
            s.add(Team(id=tid, name=name, notes=notes, sort_order=order, created_at=now, updated_at=now))
            s.flush()
            for slot, (slug, role) in enumerate(members):
                s.add(TeamMember(team_id=tid, slot=slot, character_id=ids[slug], role=role))
            for tag_id in tags:
                s.add(TeamTag(team_id=tid, tag_id=tag_id))
    with sf.begin() as s:
        # same window as the seeded "Tide of Furina" (server-local strings, Asia offset 8) in naive UTC
        b_start = datetime.strptime(start, "%Y-%m-%d %H:%M:%S") - timedelta(hours=8)
        b_end = datetime.strptime(end, "%Y-%m-%d %H:%M:%S") - timedelta(hours=8)
        primo = {"id": 201, "name": "Primogem", "icon": "", "count": 0, "rarity": 5}
        calendar = {
            "banners": [{"pool": "character", "name": "Tide of Furina", "start": iso(b_start), "end": iso(b_end),
                         "items": [{"id": 10000089, "name": "Furina", "icon": "UI_AvatarIcon_Furina", "rarity": 5},
                                   {"id": 10000032, "name": "Bennett", "icon": "UI_AvatarIcon_Bennett",
                                    "rarity": 4}]}],
            "events": [
                {"id": 9001, "name": "Fishing Festival", "description": "", "start": None,
                 "end": iso(now + timedelta(days=9)), "rewards": [{**primo, "count": 420}]},
                {"id": 9002, "name": "Quick Trial", "description": "", "start": None,
                 "end": iso(now + timedelta(hours=5)), "rewards": [{**primo, "count": 60}]},
                {"id": 9003, "name": "Photo Event", "description": "", "start": None,
                 "end": iso(now + timedelta(days=3)), "rewards": []},
            ],
            "challenges": [{"kind": "abyss", "name": "Spiral Abyss", "start": None, "end": iso(now + timedelta(days=20))},
                           {"kind": "theater", "name": "Imaginarium Theater", "start": None,
                            "end": iso(now + timedelta(days=10))}],
        }
        s.add(HoyolabSnapshot(part="calendar", data=calendar, fetched_at=now))
    engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    seed(parser.parse_args().root.resolve())
