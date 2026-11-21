export type Goal = 'none' | 'want' | 'build';
export type Status = 'building' | 'obtained' | 'wanted' | 'unobtained';

export interface Targets { level: number; normal: number; skill: number; burst: number; weapon_level: number }
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
}

export interface Artifact {
	slot: number; set_name: string; rarity: number; level: number;
	main_stat: string; substats: string[]; icon: string;
}
export interface CharacterDetail extends Character {
	artifacts: Artifact[];
	stats: { name: string; value: string }[];
	shortfall: { gaps: GapStatus; materials: CharMaterial[]; calculated: boolean } | null;
	planned_weapon: PlannedWeapon | null;
}

export interface Connection { status: 'connected' | 'expired' | 'missing'; uid: number | null }
export interface SyncPart { ok: boolean; error?: string; count?: number }
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
	gaps: GapStatus;
	pity: PityLine[];
}
export interface Settings {
	connection: Connection;
	sync_interval_minutes: number;
	default_targets: Targets;
	level_caps: number[];
	game_install_path: string;
	gamedata: {
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
}
export interface CharMaterial {
	id: number; name: string; icon: string; rarity: number; category: string; category_label: string;
	need: number; short: number; shared: boolean;
}
export interface GapStatus { computed_at: string | null; ok: boolean | null; error: string | null; stale: boolean; pending: boolean; skipped: string[] }
export interface InventoryCategory { key: string; label: string; materials: Material[] }
export interface Inventory { gaps: GapStatus; categories: InventoryCategory[] }
export interface FarmDomain { id: number; name: string; kind: 'talent' | 'weapon'; weekdays: number[]; materials: Material[]; characters: CharRef[] }
export interface WeeklyBoss { name: string; done: boolean; materials: Material[]; characters: CharRef[] }
export interface BuildingCard { character: CharRef; progress: number | null; materials: CharMaterial[]; skipped: boolean; calculated: boolean }
export interface WeaponOption { id: number; name: string; icon: string; rarity: number; weapon_type: string }
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
