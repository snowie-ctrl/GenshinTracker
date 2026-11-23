from app.domain import Targets
from app.planner.requests import PlanInput, gap_requests, has_work, share_traveler
from app.sync.hoyolab import GapCharacter, TalentIds, build_batch_body

CRYO, ANEMO, GEO = 1000000507, 1000000502, 1000000503


def inp(cid, level=80, talents=(1, 1, 1), t=Targets(90, 8, 8, 8, 90), weapon=(11401, 80), planned=False, el=7):
    return PlanInput(cid, "X", level, talents, t, weapon, avatar_id=10000007, element_attr_id=el,
                     weapon_planned=planned)


def test_carrier_takes_highest_level_and_weapon_others_talents_only():
    a = inp(ANEMO, t=Targets(80, 6, 6, 6, 80), el=2)
    c = inp(CRYO, t=Targets(90, 8, 8, 8, 90), el=7)
    out = {i.character_id: i for i in share_traveler([a, c], current=CRYO)}
    assert out[CRYO].targets.level == 90 and out[CRYO].targets.weapon_level == 90 and out[CRYO].weapon == (11401, 80)
    assert out[ANEMO].targets.level == 80 and out[ANEMO].weapon is None      # 80 = its current level
    assert out[ANEMO].targets.normal == 6


def test_carrier_is_lowest_id_when_current_has_no_goal_and_level_only_element_drops():
    a = inp(ANEMO, t=Targets(90, 1, 1, 1, 80), el=2)            # only level work
    g = inp(GEO, t=Targets(80, 8, 8, 8, 80), el=3)
    out = {i.character_id: i for i in share_traveler([g, a], current=CRYO)}
    assert out[ANEMO].targets.level == 90                        # carrier (lowest id) gets the max level
    assert out[GEO].targets.level == 80 and out[GEO].weapon is None
    reqs = gap_requests([i for i in out.values() if has_work(i)],
                        {ANEMO: TalentIds(731, 732, 739), GEO: TalentIds(731, 932, 939)})
    assert {r.character_id for r in reqs} == {ANEMO, GEO}
    geo = next(r for r in reqs if r.character_id == GEO)
    assert (geo.level_current, geo.level_target, geo.weapon, geo.avatar_id, geo.element_attr_id) == (
        80, 80, None, 10000007, 3)


def test_planned_weapon_of_another_element_moves_to_carrier():
    a = inp(ANEMO, el=2, weapon=(11509, 1), planned=True)
    c = inp(CRYO, el=7, weapon=(11401, 80))
    out = {i.character_id: i for i in share_traveler([a, c], current=CRYO)}
    assert out[CRYO].weapon == (11509, 1) and out[ANEMO].weapon is None


def test_non_travelers_untouched():
    b = PlanInput(10000032, "Bennett", 80, (6, 8, 8), Targets(90, 8, 8, 8, 90), (11401, 90), avatar_id=10000032,
                  element_attr_id=None, weapon_planned=False)
    assert share_traveler([b], current=None) == [b]


def test_batch_body_sends_body_id_and_element():
    body = build_batch_body([GapCharacter(CRYO, 80, 90, ((832, 1, 8),), None, avatar_id=10000007, element_attr_id=7),
                             GapCharacter(10000032, 80, 90, (), None)], 800000001, "os_usa")
    assert body["items"][0]["avatar_id"] == 10000007 and body["items"][0]["element_attr_id"] == 7
    assert body["items"][1]["avatar_id"] == 10000032 and "element_attr_id" not in body["items"][1]
