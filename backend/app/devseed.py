"""Fake data for demos and end-to-end tests: python -m app.devseed --root PATH"""
import argparse
from datetime import datetime
from pathlib import Path

from app.config import Paths
from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import CharacterGoal, GameCharacter, GameMeta
from app.sync.hoyolab import ArtifactInfo, DetailEntry, NotesInfo, RosterEntry, WeaponInfo
from app.sync.persist import save_details, save_notes, save_roster
from app.timeutil import iso, utcnow

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
WEAPON = WeaponInfo("Favonius Sword", "https://enka.network/ui/UI_EquipIcon_Sword_Favonius.png", 4, 90, 3)


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
    engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    seed(parser.parse_args().root.resolve())
