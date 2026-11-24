export type Goal = 'none' | 'want' | 'build';
export type Status = 'building' | 'obtained' | 'wanted' | 'unobtained';

export interface Targets {
	level: number; normal: number; skill: number; burst: number; weapon_level: number;
	constellation?: number | null; refinement?: number | null;
}
export type TalentRole = 'normal' | 'skill' | 'burst';
export interface Segment { text: string; color: string | null; italic: boolean }
export interface ScaleRow { label: string; values: string[] }
export interface KitTalent {
	name: string; icon: string | null; role: TalentRole | 'other'; cooldown: number | null; cost: number | null;
	description: Segment[][]; scaling: ScaleRow[];
}
export interface KitPassive { name: string; icon: string | null; description: Segment[][] }
export interface KitConstellation {
	index: number; name: string; icon: string | null; description: Segment[][]; raises: TalentRole | null;
}
export interface Kit { talents: KitTalent[]; passives: KitPassive[]; constellations: KitConstellation[] }
export interface KitResponse { state: 'fresh' | 'stale' | 'unavailable'; kit: Kit | null }
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
	release_at: string | null;
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
	priority: number | null;
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
	commissions_done: number; commissions_max: number; commission_bonus_claimed: boolean | null;
	realm_currency: number; realm_currency_max: number; realm_currency_full_at: string | null;
	expeditions: Expedition[]; expeditions_max: number | null; fetched_at: string;
}
export interface Timer { kind: 'resin' | 'realm' | 'transformer' | 'expedition'; label: string; icon: string; ready_at: string }
export interface DayFarm { weekday: number; domains: FarmDomain[] }
export interface BuildMaterial {
	id: number; name: string; icon: string; rarity: number; category: string; category_label: string;
	need: number; have: number; craft: number;
}
export interface BuildCard {
	character: CharRef; priority: number; progress: number | null; calculated: boolean; ready: boolean;
	materials: BuildMaterial[];
}
export interface PriorityResult { builds: BuildCard[]; completed: CharRef[] }
export interface DashEvent extends EventRow { kind: 'event' }
export interface DashReset { kind: 'reset'; id: string; key: string; name: string; end: string; done: false }
export type DashEventItem = DashEvent | DashReset;
export interface Dashboard {
	connection: Connection;
	display_name: string;
	notes: Notes | null;
	timers: Timer[];
	ending_soon: EventRow[];
	server_weekday: number;
	domains_by_day: Record<string, DayFarm>;
	weekly_bosses: { discounts_left: number | null; discounts_max: number | null; bosses: WeeklyBoss[] };
	builds: BuildCard[];
	completed: CharRef[];
	live_banners: DashBanner[];
	events: DashEventItem[];
	calendar_fetched_at: string | null;
	gaps: GapStatus;
}
export interface StatTile { key: string; label: string; value: number | string; detail?: { label: string; value: number }[] }
export interface RegionView {
	id: number; name: string; explored: number; reputation: number | null; icon: string | null;
	offerings: { name: string; level: number; icon: string | null }[]; areas: { name: string; explored: number }[];
}
export interface TeapotView {
	level: number; comfort: number; comfort_name: string; comfort_icon: string; items: number; visitors: number;
	realms: { name: string; icon: string }[];
}
export interface ProfileHeaderView { name: string; ar: number; days_active: number; achievements: number }
export interface ProfileView {
	header: ProfileHeaderView; tiles: StatTile[]; regions: RegionView[]; teapot: TeapotView | null;
	bosses: { name: string; kills: number }[];
}
export interface RosterView {
	total: number; elements: Record<string, number>; weapon_types: Record<string, number>;
	rarity: { '5': number; '4': number }; constellations: number; c6: number;
}
export interface ShowcaseArtifact {
	slot: number; set_name: string; icon: string; rarity: number; level: number; main_stat: string; substats: string[];
}
export interface ShowcaseEntry {
	id: number; slug: string | null; name: string; rarity: number | null; element: string | null; icon: string | null;
	level: number; constellation: number; friendship: number;
	talents: { normal: number | null; skill: number | null; burst: number | null };
	weapon: { name: string; icon: string; level: number; refinement: number; rarity: number };
	stats: { name: string; value: string }[]; artifacts: ShowcaseArtifact[]; sets: string; crit_value: number;
}
export interface OwnedOption { id: number; name: string; icon: string | null }
export interface TeamChar { id: number; name: string; icon: string | null }
export interface ChallengeRunView { season: string; start: string | null; end: string | null; summary: Record<string, number | string>; teams: TeamChar[][] }
export interface ChallengeViews { abyss: { current: ChallengeRunView | null; past: ChallengeRunView[] }; theater: { current: ChallengeRunView | null; past: ChallengeRunView[] }; stygian: { current: ChallengeRunView | null; past: ChallengeRunView[] } }
export interface ProfileResponse {
	connected: boolean; fetched_at: string | null; error: string | null; profile: ProfileView | null;
	roster: RosterView; showcase: ShowcaseEntry[]; showcase_mode: 'auto' | 'custom'; owned: OwnedOption[];
	challenges: ChallengeViews;
}
export type MapKey = 'hoyolab' | 'appsample';
export interface MapInfo { key: MapKey; name: string; url: string; allowed: boolean | null }
export interface MapsResponse { maps: MapInfo[]; default_map: MapKey }
export interface Settings {
	default_map: MapKey;
	connection: Connection;
	sync_interval_minutes: number;
	level_caps: number[];
	game_install_path: string;
	good_import_enabled: boolean;
	background_animated: boolean;
	display_name: string;
	gamedata: {
		artifact_sets: { fetched_at: string | null; last_error: string | null; count: number };
		artifact_domains: { fetched_at: string | null; last_error: string | null; count: number; unmatched: string[] };
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
	avg_pity: number | null; fives: WishPull[]; fours: WishPull[];
}
export type WishFilter = 'all' | 'character' | 'weapon' | 'chronicled' | 'standard';
export interface AnalysisPull extends WishPull { pool: Pool }
export interface Rotation {
	label: string; version: string; start: string; pool_counts: Partial<Record<Pool, number>>; pulls: number;
	fives: { name: string; icon: string | null }[];
}
export interface TierCounts { five: Record<string, number>; four: Record<string, number> }
export interface Luck {
	avg_pity: number | null; expected: number; verdict: 'luckier' | 'average' | 'unluckier' | null;
	won: number | null; lost: number | null; rate: number | null; judged_label: string | null;
}
export interface AnalysisBlock {
	months: MonthRow[]; rotations: Rotation[]; elements: TierCounts; weapon_types: TierCounts; unknown_items: number;
	pity_hist: { buckets: { bucket: string; count: number }[]; soft: number | null; avg: number | null };
	primogems: { points: { date: string; total: number }[]; fives: { date: string; name: string; icon: string | null; total: number }[] };
	luck: Luck; fives: AnalysisPull[]; fours: AnalysisPull[];
}
export interface WishImport {
	id: number; source: 'game' | 'uigf' | 'paimon'; started_at: string; finished_at: string | null;
	ok: boolean | null; added: number; upgraded: number; skipped: number; error: string | null;
}
export interface ImportStatus { running: boolean; last: WishImport | null }
export interface MonthRow { month: string; character: number; weapon: number; chronicled: number; standard: number; beginner: number }
export interface BannerRow { key: string; pool: Pool; name: string; short_name: string; start: string; pulls: number; fives: string[] }
export interface WishSummary {
	pools: PoolSummary[]; overall: WishStats; analysis: Partial<Record<WishFilter, AnalysisBlock>>;
	banners: BannerRow[]; banners_available: boolean; import: ImportStatus;
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
export interface ArtifactSetRef { name: string; icon: string | null; pieces: number }
export interface TeamMember {
	id: number; name: string; slug: string | null; icon: string | null; element: string | null; rarity: number;
	owned: boolean; goal: Goal; status: Status; prefarming: boolean; level: number | null; talents: Talents | null;
	weapon: Weapon | null; progress: number | null; role: string; artifact_line: string;
	not_building: boolean; not_calculated: boolean;
	splash: string | null; constellation: number | null; artifact_sets: ArtifactSetRef[];
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
export interface SaveTeamResponse { team: Team; raised: number[]; lowered: number[] }
export interface DeleteTeamResponse { ok: boolean; lowered: number[] }
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
export interface DashBanner extends LiveBanner { pity: PityLine | null }
export interface Reward { id: number; name: string; icon: string; count: number; rarity: number }
export interface EventRow {
	id: number; name: string; description: string; start: string | null; end: string | null;
	rewards: Reward[]; primogems: number; done: boolean; finished: boolean; ending_soon: boolean;
}
export interface EventsLeft { count: number; primogems: number }
export interface ResetRow { key: 'daily' | 'weekly' | 'abyss' | 'theater' | 'stygian'; label: string; at: string }
export interface HistoryItem { id: number; name: string; icon: string | null; rarity: number }
export interface TimelineRow {
	key: string; kind: 'event' | 'wish'; pool: 'character' | 'weapon' | 'chronicled' | null; name: string;
	start: string | null; end: string | null; image: string | null; description: string; calendar_id: number | null;
	rewards: Reward[]; primogems: number; finished: boolean; done: boolean; ending_soon: boolean;
	items: { featured_5: HistoryItem[]; featured_4: HistoryItem[] } | null; pulls: BannerPulls | null;
}
export interface EndingSoon { key: string; kind: 'event' | 'wish'; name: string; end: string }
export interface EventsResponse {
	connected: boolean; fetched_at: string | null; error: string | null;
	banners: { current: LiveBanner[]; upcoming: LiveBanner[] };
	events: EventRow[]; events_left: EventsLeft; resets: ResetRow[];
	timeline: TimelineRow[]; ending_soon: EndingSoon[]; announcements_error: string | null;
}
export interface HistoryBanner {
	key: string; pool: 'character' | 'weapon' | 'chronicled'; name: string;
	featured_5: HistoryItem[]; featured_4: HistoryItem[]; pulls: BannerPulls | null;
}
export interface HistoryPhase { start: string; end: string; upcoming: boolean; image: string | null; banners: HistoryBanner[] }
export interface HistoryVersion { version: string; phases: HistoryPhase[] }
export interface BannerHistoryPage { total_versions: number; page: number; page_size: number; versions: HistoryVersion[] }

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
