from datetime import datetime, timedelta

from app.db.models import GameBanner, Wish, WishChart
from app.wishes import pity as pity_mod
from app.wishes.pity import attribute, banner_windows, summarize_pool

FURINA, NAHIDA, DILUC = 10000089, 10000073, 10000016
MIST, DREAMS, WOLF = 11509, 14504, 12502
NAMES = {FURINA: "Furina", NAHIDA: "Nahida", DILUC: "Diluc", MIST: "Mistsplitter Reforged",
         DREAMS: "A Thousand Floating Dreams", WOLF: "Wolf's Gravestone"}


def banner(pool, start, end, order=0, f5=(), tz=False, tz_end=False, name="B"):
    return GameBanner(key=f"{pool}|{start}|{order}", pool=pool, name=name, short_name=name, start=start, end=end,
                      timezone_dependent=tz, timezone_dependent_end=tz_end, order=order, featured_5=list(f5),
                      featured_4=[], version="4.3")


def pulls(pool, items, start="2024-01-15 10:00:00", gacha_type="301"):
    """items: 3 / 4 for filler, or (rarity, item_id) tuples. One pull per minute."""
    t0 = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    out = []
    for i, it in enumerate(items):
        rarity, item_id = (it, None) if isinstance(it, int) else it
        gt = gacha_type[i] if isinstance(gacha_type, list) else gacha_type
        out.append(Wish(pk=i + 1, id=None, pool=pool, gacha_type=gt,
                        time=(t0 + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S"), seq=0,
                        name=NAMES.get(item_id, "Filler"), item_id=item_id if rarity == 5 else 999,
                        item_type="character", rarity=rarity, source="game", imported_at=t0))
    return out


CHAR_WINDOWS = [banner("character", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [FURINA], name="Furina"),
                banner("character", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 1, [NAHIDA], name="Nahida")]


def summ(pool, rows, banners=(), chart=None, now_local="2024-01-20 00:00:00", offset=8):
    return summarize_pool(pool, rows, banner_windows(banners, offset).get(pool, []), chart, now_local, offset, NAMES)


def test_pity_counts_reset_and_carry_over():
    r = summ("standard", pulls("standard", [3, 3, 4, 3, (5, DILUC), 3, 3, 4, 3], gacha_type="200"))
    assert r.total == 9 and [p.pity for p in r.fives] == [5]
    assert [p.pity for p in r.fours] == [3, 3]
    assert (r.pity5, r.pity4, r.hard, r.next_state) == (4, 1, 90, None)


def test_soft_flag():
    r = summ("character", pulls("character", [3] * 73))
    assert r.pity5 == 73 and r.in_soft


def test_character_outcomes_and_next_state():
    rows = pulls("character", [3, (5, DILUC), 3, (5, FURINA), (5, FURINA), (5, NAHIDA)],
                 gacha_type=["301", "301", "301", "301", "301", "400"])
    r = summ("character", rows, CHAR_WINDOWS)
    assert [p.outcome for p in r.fives] == ["lost", "guaranteed", "won", "won"]
    assert [p.banner for p in r.fives] == ["Furina", "Furina", "Furina", "Nahida"]
    assert r.next_state == "50/50"
    r = summ("character", rows + pulls("character", [(5, DILUC)], start="2024-01-16 10:00:00"), CHAR_WINDOWS)
    assert r.next_state == "guaranteed"


def test_no_banner_data_means_unknown_not_wrong():
    r = summ("character", pulls("character", [(5, FURINA), 3]))
    assert [p.outcome for p in r.fives] == ["unknown"] and r.next_state == "unknown"
    assert r.pity5 == 1                                       # pity is still exact


def test_unknown_then_featured_is_unknown_then_known_again():
    early = pulls("character", [(5, DILUC)], start="2023-12-01 10:00:00")        # before any banner
    later = pulls("character", [(5, FURINA), (5, FURINA)], start="2024-01-15 10:00:00")
    for i, w in enumerate(later):
        w.pk = 10 + i
    r = summ("character", early + later, CHAR_WINDOWS)
    assert [p.outcome for p in r.fives] == ["unknown", "unknown", "won"]


def test_unknown_item_name_is_unknown():
    rows = pulls("character", [(5, FURINA)])
    rows[0].item_id = None
    assert summ("character", rows, CHAR_WINDOWS).fives[0].outcome == "unknown"


def test_rows_without_gacha_type_use_the_featured_banner():
    rows = pulls("character", [(5, NAHIDA), (5, DILUC)], gacha_type=None)
    r = summ("character", rows, CHAR_WINDOWS)
    assert [(p.outcome, p.banner) for p in r.fives] == [("won", "Nahida"), ("lost", "Furina")]


def test_timezone_dependent_times_shift_to_server_time():
    b = [banner("character", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [FURINA], tz=True, tz_end=True)]
    w = pulls("character", [(5, FURINA)], start="2024-01-09 18:00:00")[0]
    assert attribute(w, banner_windows(b, -5)["character"]) is not None    # starts 2024-01-09 17:00 in America
    assert attribute(w, banner_windows(b, 8)["character"]) is None
    late = pulls("character", [(5, FURINA)], start="2024-01-30 12:00:00")[0]
    assert attribute(late, banner_windows(b, 1)["character"]) is None       # ends 10:59 in Europe


def test_weapon_75_25():
    wb = [banner("weapon", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [MIST, DREAMS], name="Mist")]
    r = summ("weapon", pulls("weapon", [(5, WOLF), (5, DREAMS)], gacha_type="302"), wb)
    assert [p.outcome for p in r.fives] == ["lost", "guaranteed"] and r.next_state == "75/25"
    assert r.hard == 80


def test_fate_points_follow_the_chart():
    wb = [banner("weapon", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [MIST, DREAMS], name="Mist")]
    chart = WishChart(pool="weapon", item_id=MIST, set_at=datetime(2024, 1, 15, 0, 0))   # 08:00 local (UTC+8)
    rows = pulls("weapon", [3, (5, DREAMS)], start="2024-01-15 10:00:00", gacha_type="302")
    r = summ("weapon", rows, wb, chart)
    assert r.fate["points"] == 1 and r.fate["chart_name"] == "Mistsplitter Reforged"
    assert [c["item_id"] for c in r.fate["choices"]] == [MIST, DREAMS]
    rows += pulls("weapon", [(5, MIST)], start="2024-01-16 10:00:00", gacha_type="302")
    rows[-1].pk = 99
    assert summ("weapon", rows, wb, chart).fate["points"] is None           # chart used up
    old = WishChart(pool="weapon", item_id=MIST, set_at=datetime(2024, 1, 1))
    assert summ("weapon", rows[:2], wb, old).fate["points"] is None         # set before this banner


def test_chronicled_chart_marks_outcomes():
    cb = [banner("chronicled", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [FURINA, MIST], name="Ode")]
    chart = WishChart(pool="chronicled", item_id=FURINA, set_at=datetime(2024, 1, 15, 0, 0))
    r = summ("chronicled", pulls("chronicled", [(5, MIST)], gacha_type="500"), cb, chart)
    assert r.fives[0].outcome == "not_charted" and r.fate["points"] == 1


def test_radiance_counts_losses_since_5_0(monkeypatch):
    monkeypatch.setattr(pity_mod, "RADIANCE_LIKELY_AT", 2)
    cw = [banner("character", "2024-01-01 00:00:00", "2025-12-31 00:00:00", 0, [FURINA])]
    before = pulls("character", [(5, DILUC), (5, FURINA)], start="2024-08-01 10:00:00")
    after = pulls("character", [(5, DILUC), (5, FURINA), (5, DILUC)], start="2024-09-01 10:00:00")
    for i, w in enumerate(after):
        w.pk = 50 + i
    r = summ("character", before + after, cw)
    assert r.radiance == {"losses": 2, "likely": True, "estimate": True}   # guarantee keeps the count
    won = pulls("character", [(5, FURINA)], start="2024-10-01 10:00:00")
    won[0].pk = 90
    r = summ("character", before + after + pulls("character", [(5, FURINA)], start="2024-09-20 10:00:00") + won, cw)
    assert r.radiance["losses"] == 0


def test_weapon_banner_with_incomplete_featured_list_is_unknown():
    wb = [banner("weapon", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [], name="Mist")]
    r = summ("weapon", pulls("weapon", [(5, DREAMS)], gacha_type="302"), wb)
    assert [p.outcome for p in r.fives] == ["unknown"] and r.next_state == "unknown"


def test_wanted_banner_order_missing_is_unattributed_not_guessed():
    # Two overlapping character banners, both order 0: a 400 (second banner) pull has no banner to match.
    cb = [banner("character", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [FURINA], name="Furina"),
          banner("character", "2024-01-12 06:00:00", "2024-01-30 17:59:00", 0, [NAHIDA], name="Nahida")]
    r = summ("character", pulls("character", [(5, NAHIDA)], gacha_type="400"), cb)
    assert r.fives[0].outcome == "unknown" and r.fives[0].banner is None and r.next_state == "unknown"
