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
}
export interface Settings {
	connection: Connection;
	sync_interval_minutes: number;
	default_targets: Targets;
	level_caps: number[];
	gamedata: {
		fetched_at: string | null; last_error: string | null; count: number;
		materials: { fetched_at: string | null; last_error: string | null; count: number };
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
