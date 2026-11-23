export type Goal = 'none' | 'want' | 'build';
export type Status = 'building' | 'obtained' | 'wanted' | 'unobtained';

export interface Targets { level: number; normal: number; skill: number; burst: number; weapon_level: number }
export interface TravelerInfo {
	element_id: number; current: boolean; seen: boolean; unlocked: boolean;
	talents: Talents; constellation: number; source: 'sync' | 'manual';
}
export interface Talents { normal: number; skill: number; burst: number }
export interface Weapon { name: string; icon: string; rarity: number; level: number; refinement: number }

export interface Character {
	id: number;
	slug: string;
	name: string;
	rarity: number;
	element: string | null;
	weapon_type: string | null;
	icon: string | null;
	splash: string | null;
	owned: boolean;
	level: number | null;
	constellation: number | null;
	friendship: number | null;
	talents: Talents | null;
	weapon: Weapon | null;
	goal: Goal;
	targets: Targets | null;
	status: Status;
	prefarming: boolean;
	progress: number | null;
	planned_weapon_id: number | null;
	team_tags: number[][];
}

export interface Artifact {
	slot: number; set_name: string; rarity: number; level: number;
	main_stat: string; substats: string[]; icon: string;
}
export interface CharacterDetail extends Character {
	traveler: TravelerInfo | null;
	artifacts: Artifact[];
	stats: { name: string; value: string }[];
	shortfall: { gaps: GapStatus; materials: CharMaterial[]; calculated: boolean } | null;
	planned_weapon: PlannedWeapon | null;
	teams: TeamRef[];
}

export interface Connection { status: 'connected' | 'expired' | 'missing'; uid: number | null }
export interface SyncPart { ok: boolean; error?: string; count?: number; skipped?: 'fresh' | string[] }
export interface SyncRun {
	id: number; trigger: string; started_at: string; finished_at: string | null;
	parts: Record<string, SyncPart>;
}
export interface SyncStatus { running: boolean; runs: SyncRun[] }

export interface Expedition { icon: string; finished: boolean; return_at: string }
export interface Notes {
	resin: number; resin_max: number; resin_full_at: string;
	commissions_done: number; commissions_max: number;
	realm_currency: number; realm_currency_max: number;
	expeditions: Expedition[]; fetched_at: string;
}
export interface Dashboard {
	connection: Connection;
	notes: Notes | null;
	building: { count: number; average_progress: number | null };
	farm_today: { weekday: number; domains: FarmDomain[] };
	weekly_bosses: { discounts_left: number | null; discounts_max: number | null; bosses: WeeklyBoss[] };
	building_cards: BuildingCard[];
	build_teams: BuildTeamCard[];
	gaps: GapStatus;
	pity: PityLine[];
	live_banners: LiveBanner[];
	events_left: EventsLeft & { next: EventRow[] };
	resets: ResetRow[];
	calendar_fetched_at: string | null;
	profile_summary: { ar: number | null; fetched_at: string | null; abyss_stars: number | null; theater_act: number | null };
}
export interface StatTile { label: string; value: number }
export interface RegionView { id: number; name: string; explored: number; reputation: number | null; offerings: { name: string; level: number }[] }
export interface ProfileView { ar: number; days_active: number; tiles: StatTile[]; chests: StatTile[]; oculi: StatTile[]; regions: RegionView[] }
export interface TeamChar { id: number; name: string; icon: string | null }
export interface ChallengeRunView { season: string; start: string | null; end: string | null; summary: Record<string, number | string>; teams: TeamChar[][] }
export interface ChallengeViews { abyss: { current: ChallengeRunView | null; past: ChallengeRunView[] }; theater: { current: ChallengeRunView | null; past: ChallengeRunView[] }; stygian: { current: ChallengeRunView | null; past: ChallengeRunView[] } }
export interface ProfileResponse { connected: boolean; fetched_at: string | null; error: string | null; profile: ProfileView | null; challenges: ChallengeViews }
export type MapKey = 'hoyolab' | 'appsample';
export interface MapInfo { key: MapKey; name: string; url: string; allowed: boolean | null }
export interface MapsResponse { maps: MapInfo[]; default_map: MapKey }
export interface Settings {
	default_map: MapKey;
	connection: Connection;
	sync_interval_minutes: number;
	default_targets: Targets;
	level_caps: number[];
	game_install_path: string;
	good_import_enabled: boolean;
	background_animated: boolean;
	gamedata: {
		artifact_sets: { fetched_at: string | null; last_error: string | null; count: number };
		fetched_at: string | null; last_error: string | null; count: number;
		materials: { fetched_at: string | null; last_error: string | null; count: number };
		banners: { fetched_at: string | null; last_error: string | null; count: number; unmapped: string[] };
	};
}
export interface Account { uid: number; server: string; nickname: string; level: number }
export type ConnectResponse = { status: 'connected'; uid: number } | { status: 'choose'; accounts: Account[] };

export type MaterialState = 'short' | 'met' | 'unneeded';
export interface MaterialSource { kind: 'domain' | 'weekly_boss' | 'region' | 'text'; name: string; days: number[] }
export interface CharRef { id: number; name: string; slug: string; icon: string | null }
export interface Needer extends CharRef { need: number }
export interface Material {
	id: number; name: string; icon: string; rarity: number; category: string; state: MaterialState;
	need: number; short: number; have: number | null; craftable: number; to_farm: number;
	sources: MaterialSource[]; characters: Needer[];
	scan?: number | null;
}
export interface CharMaterial {
	id: number; name: string; icon: string; rarity: number; category: string; category_label: string;
	need: number; short: number; shared: boolean;
}
export interface GapStatus { computed_at: string | null; ok: boolean | null; error: string | null; stale: boolean; pending: boolean; skipped: string[] }
export interface InventoryCategory { key: string; label: string; materials: Material[] }
export interface Inventory { gaps: GapStatus; categories: InventoryCategory[]; good: GoodRef | null }
export interface FarmDomain { id: number; name: string; kind: 'talent' | 'weapon'; weekdays: number[]; materials: Material[]; characters: CharRef[] }
export interface WeeklyBoss { name: string; done: boolean; materials: Material[]; characters: CharRef[] }
export interface BuildingCard { character: CharRef; progress: number | null; materials: CharMaterial[]; skipped: boolean; calculated: boolean }
export interface WeaponOption { id: number; name: string; icon: string; rarity: number; weapon_type: string; owned?: OwnedWeapon | null }
export interface PlannedWeapon { id: number; name: string; icon: string; rarity: number; equipped: boolean }

export type Pool = 'character' | 'weapon' | 'chronicled' | 'standard' | 'beginner';
export type Outcome = 'won' | 'lost' | 'guaranteed' | 'unknown' | 'charted' | 'not_charted';
export interface WishPull {
	name: string; item_id: number | null; icon: string | null; item_type: 'character' | 'weapon';
	rarity: number; time: string; pity: number; outcome: Outcome | null; banner: string | null;
}
export interface Fate {
	points: number | null; max: number; chart_item_id: number | null; chart_name: string | null;
	choices: { item_id: number; name: string }[]; banner: string | null;
}
export interface Radiance { losses: number | null; likely: boolean | null; estimate: boolean }
export interface WishStats {
	pulls: number; primogems: number; five: number; four: number; avg_five_pity: number | null;
	won: number; lost: number; win_rate: number | null;
}
export interface PoolSummary {
	pool: Pool; total: number; pity5: number; pity4: number; hard: number; soft: number | null; in_soft: boolean;
	next_state: string | null; fate: Fate | null; radiance: Radiance | null; stats: WishStats;
	fives: WishPull[]; fours: WishPull[];
}
export interface WishImport {
	id: number; source: 'game' | 'uigf' | 'paimon'; started_at: string; finished_at: string | null;
	ok: boolean | null; added: number; upgraded: number; skipped: number; error: string | null;
}
export interface ImportStatus { running: boolean; last: WishImport | null }
export interface MonthRow { month: string; character: number; weapon: number; chronicled: number; standard: number; beginner: number }
export interface BannerRow { key: string; pool: Pool; name: string; short_name: string; start: string; pulls: number; fives: string[] }
export interface WishSummary {
	pools: PoolSummary[]; overall: WishStats;
	charts: { monthly: MonthRow[]; pity_histogram: { bucket: string; count: number }[]; banners: BannerRow[] };
	banners_available: boolean; import: ImportStatus;
}
export interface HistoryRow {
	time: string; name: string; item_id: number | null; icon: string | null; item_type: 'character' | 'weapon';
	rarity: number; pool: Pool; banner: string | null; banner_key: string | null; pity: number | null;
}
export interface HistoryPage { total: number; page: number; page_size: number; rows: HistoryRow[] }
export interface HistoryFilters { pool: Pool | ''; rarity: number | ''; type: 'character' | 'weapon' | ''; banner: string; q: string }
export interface CacheStatus { status: 'found' | 'no_link' | 'not_found' | 'locked'; cached_at: string | null }
export interface PityLine { pool: Pool; pity5: number; hard: number; next_state: string | null; fate_points: number | null }

export interface Tag { id: number; name: string; color: string; builtin: boolean }
export interface TagWithCount extends Tag { team_count: number }
export interface TeamMember {
	id: number; name: string; slug: string | null; icon: string | null; element: string | null; rarity: number;
	owned: boolean; goal: Goal; status: Status; prefarming: boolean; level: number | null; talents: Talents | null;
	weapon: Weapon | null; progress: number | null; role: string; artifact_line: string;
	not_building: boolean; not_calculated: boolean;
}
export interface TeamMaterial {
	id: number; name: string; icon: string; rarity: number; category: string; category_label: string;
	need: number; short: number; craftable: number; to_farm: number; shared: boolean;
}
export interface Team {
	id: number; name: string; notes: string; sort_order: number; tags: Tag[]; has_build_tag: boolean;
	members: TeamMember[]; shortfall: TeamMaterial[] | null; progress: number | null;
}
export interface TeamsResponse { gaps: GapStatus; connected: boolean; teams: Team[] }
export interface TeamResponse { gaps: GapStatus; connected: boolean; team: Team }
export interface MemberDraft { character_id: number; role: string }
export interface TeamBody { name: string; notes: string; members: MemberDraft[]; tag_ids: number[]; new_tags: string[] }
export interface SaveTeamResponse { team: Team; raised: number[] }
export interface BuildTeamCard {
	id: number; name: string; members: CharRef[]; progress: number | null; top: TeamMaterial[]; more: number;
	has_shortfall: boolean; all_calculated: boolean; short_count: number;
}
export interface TeamRef { id: number; name: string; tags: Tag[] }

export interface BannerItem { id: number; name: string; icon: string; rarity: number; kind: 'character' | 'weapon' }
export interface BannerPulls { pulls: number; fives: string[]; fours: string[] }
export interface LiveBanner {
	id: number; pool: 'character' | 'weapon' | 'chronicled'; name: string; version: string;
	start: string | null; end: string | null; items: BannerItem[]; pulls: BannerPulls | null;
}
export interface Reward { id: number; name: string; icon: string; count: number; rarity: number }
export interface EventRow {
	id: number; name: string; description: string; start: string | null; end: string | null;
	rewards: Reward[]; primogems: number; done: boolean; ending_soon: boolean;
}
export interface EventsLeft { count: number; primogems: number }
export interface ResetRow { key: 'daily' | 'weekly' | 'abyss' | 'theater' | 'stygian'; label: string; at: string }
export interface EventsResponse {
	connected: boolean; fetched_at: string | null; error: string | null;
	banners: { current: LiveBanner[]; upcoming: LiveBanner[] };
	events: EventRow[]; events_left: EventsLeft; resets: ResetRow[];
}
export interface HistoryItem { id: number; name: string; icon: string | null; rarity: number }
export interface HistoryBanner {
	key: string; name: string; short_name: string; start: string; end: string;
	featured_5: HistoryItem[]; featured_4: HistoryItem[]; pulls: BannerPulls | null;
}
export interface BannerHistoryPage { total: number; page: number; page_size: number; rows: HistoryBanner[] }

export interface GoodRef { imported_at: string; source: string | null }
export interface GoodCounts {
	materials: { matched: number; ignored: number; unmatched: number };
	weapons: { matched: number; unmatched: number };
	artifacts: { matched: number; unmatched: number };
}
export interface GoodSummary { imported_at: string; source: string | null; counts: GoodCounts; unmatched: string[] }
export interface GoodStatus { enabled: boolean; imported_at: string | null; source: string | null; counts: GoodCounts | null; unmatched: string[] }
export interface OwnedWeapon { count: number; best_level: number; best_refinement: number }
export interface GoodWeapon {
	id: number; weapon_id: number; name: string; icon: string; rarity: number; weapon_type: string; level: number;
	ascension: number; refinement: number; lock: boolean; location: string | null; holder: CharRef | null;
}
export type ArtifactSlot = 'flower' | 'plume' | 'sands' | 'goblet' | 'circlet';
export interface GoodArtifact {
	id: number; set_id: number; set_name: string; icon: string; slot: ArtifactSlot; rarity: number; level: number;
	main_stat: string; substats: { key: string; value: number }[]; lock: boolean; location: string | null;
	holder: CharRef | null;
}
