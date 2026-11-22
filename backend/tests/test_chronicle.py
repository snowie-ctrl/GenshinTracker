from datetime import datetime, timezone
from types import SimpleNamespace as NS

from app.sync.chronicle import (
    character_ids, to_abyss_run, to_calendar, to_json, to_profile, to_stygian_runs, to_theater_runs,
)

T0, T1 = 1763870400, 1765166400     # 2025-11-23 04:00Z, 2025-12-08 04:00Z


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc)


def banner(id=1, chars=(), weapons=(), start=T0, end=T1, name="Tide"):
    return NS(id=id, version="6.2", name=name, type=1, characters=list(chars), weapons=list(weapons),
              start_timestamp=start, end_timestamp=end)


def char(id, rarity=5, name="Furina"):
    return NS(id=id, icon=f"https://x/{id}.png", name=name, element="Hydro", rarity=rarity)


def event(id=9001, rewards=(), **details):
    base = dict(id=id, name="Fishing Fest", description="<p>Catch <b>fish</b></p>", strategy="", type="ActTypeOther",
                start_timestamp=T0, end_timestamp=T1, status=2, countdown_seconds=10, rewards=list(rewards),
                is_finished=False, abyss_detail=None, theater_detail=None, stygian_detail=None)
    base.update(details)
    return NS(**base)


def reward(id=201, name="Primogem", num=420):
    return NS(id=id, name=name, icon="https://x/r.png", wiki_url="", num=num, rarity=5, homepage_show=True)


def test_calendar_maps_banners_events_and_challenges():
    cal = NS(
        character_banners=[banner(chars=[char(10000089), char(10000032, 4, "Bennett")])],
        weapon_banners=[banner(id=2, weapons=[NS(id=11509, icon="w", rarity=5, name="Mistsplitter", wiki_url="")])],
        chronicled_banners=[],
        events=[event(rewards=[reward(), reward(104003, "Hero's Wit", 10)])],
        challenges=[event(id=1, name="Spiral Abyss", abyss_detail=NS(unlocked=True)),
                    event(id=2, name="Imaginarium Theater", theater_detail=NS(unlocked=True)),
                    event(id=3, name="Stygian Onslaught", stygian_detail=NS(unlocked=True)),
                    event(id=4, name="Something else")],
    )
    info = to_calendar(cal)
    b = info.banners[0]
    assert (b.pool, b.start, b.end) == ("character", "2025-11-23T04:00:00Z", "2025-12-08T04:00:00Z")
    assert [(i.id, i.rarity, i.kind) for i in b.items] == [(10000089, 5, "character"), (10000032, 4, "character")]
    assert info.banners[1].pool == "weapon" and info.banners[1].items[0].kind == "weapon"
    e = info.events[0]
    assert e.description == "Catch fish"
    assert [(r.id, r.count) for r in e.rewards] == [(201, 420), (104003, 10)]
    assert [(c.kind, c.end) for c in info.challenges] == [
        ("abyss", "2025-12-08T04:00:00Z"), ("theater", "2025-12-08T04:00:00Z"), ("stygian", "2025-12-08T04:00:00Z")]
    assert character_ids(info) == {10000089, 10000032}
    assert to_json(info)["events"][0]["rewards"][0]["name"] == "Primogem"


def test_zero_timestamps_become_none_and_traveler_is_canonical():
    cal = NS(character_banners=[banner(chars=[char(10000007, name="Traveler")], start=0, end=0)],
             weapon_banners=[], chronicled_banners=[], events=[], challenges=[])
    b = to_calendar(cal).banners[0]
    assert (b.start, b.end, b.items[0].id) == (None, None, 10000005)


def test_profile_drops_identity_and_maps_regions():
    user = NS(
        info=NS(nickname="SECRET-NICK", server="os_euro", level=60, icon="i", in_game_avatar="a"),
        stats=NS(achievements=900, days_active=1200, characters=95, spiral_abyss="12-3",
                 anemoculi=66, geoculi=131, dendroculi=271, electroculi=181, hydroculi=271, pyroculi=200,
                 lunoculi=0, cryoculi=0, common_chests=3000, exquisite_chests=2000, precious_chests=600,
                 luxurious_chests=200, remarkable_chests=100, unlocked_waypoints=400, unlocked_domains=70,
                 max_friendship_characters=40),
        explorations=[NS(id=1, parent_id=0, name="Mondstadt", raw_explored=1000, type="Reputation", level=8,
                         offerings=[NS(name="Frostbearing Tree", level=12, icon="")]),
                      NS(id=9, parent_id=0, name="Enkanomiya", raw_explored=987, type="Offering", level=0,
                         offerings=[])],
        characters=[], teapot=None,
    )
    p = to_profile(user)
    assert (p.stats.ar, p.stats.days_active, p.stats.achievements) == (60, 1200, 900)
    assert p.stats.oculi["anemoculi"] == 66 and p.stats.chests["luxurious"] == 200
    assert [(r.name, r.explored, r.reputation) for r in p.regions] == [("Mondstadt", 100.0, 8), ("Enkanomiya", 98.7, None)]
    assert "SECRET-NICK" not in str(to_json(p))
    assert "os_euro" not in str(to_json(p))


def abyss(battles=12, season=101):
    team = [NS(id=10000089), NS(id=10000032)]
    return NS(unlocked=True, season=season, start_time=utc(T0), end_time=utc(T1), total_battles=battles,
              total_wins=battles, max_floor="12-3", total_stars=36,
              floors=[NS(floor=12, stars=9, chambers=[NS(chamber=1, stars=3, battles=[NS(half=1, characters=team)])])])


def test_abyss_run():
    run = to_abyss_run(abyss())
    assert (run.kind, run.season, run.start) == ("abyss", "101", "2025-11-23T04:00:00Z")
    assert run.summary == {"stars": 36, "max_floor": "12-3", "wins": 12, "battles": 12}
    assert run.teams == [[10000089, 10000032]]


def test_abyss_not_attempted_gives_none():
    assert to_abyss_run(abyss(battles=0)) is None
    assert to_abyss_run(NS(unlocked=False, season=1, start_time=utc(T0), end_time=utc(T1), total_battles=0,
                           total_wins=0, max_floor="0-0", total_stars=0, floors=[])) is None


def test_theater_and_stygian_runs():
    act = NS(characters=[NS(id=10000073), NS(id=10000025)])
    theater = NS(unlocked=True, datas=[
        NS(has_data=True, acts=[act, act], stats=NS(difficulty=3, best_record=10, medal_num=8),
           schedule=NS(id=77, start_datetime=utc(T0), end_datetime=utc(T1))),
        NS(has_data=False, acts=[], stats=NS(difficulty=0, best_record=0, medal_num=0),
           schedule=NS(id=76, start_datetime=utc(T0), end_datetime=utc(T1))),
    ])
    runs = to_theater_runs(theater)
    assert [(r.season, r.summary) for r in runs] == [("77", {"act": 10, "difficulty": 3, "medals": 8})]
    assert runs[0].teams == [[10000073, 10000025], [10000073, 10000025]]
    sty = [NS(season=NS(id=5, name="S", start_at=utc(T0), end_at=utc(T1)),
              single_player=NS(has_data=True, best_record=NS(difficulty=4, time_used=95, icon=""),
                               challenges=[NS(team=[NS(id=10000089)])]),
              multi_player=NS(has_data=False, best_record=None, challenges=[]))]
    s = to_stygian_runs(sty)
    assert [(r.kind, r.season, r.summary, r.teams) for r in s] == [
        ("stygian", "5", {"difficulty": 4, "time_used": 95}, [[10000089]])]
    assert to_theater_runs(NS(unlocked=False, datas=[])) == []
