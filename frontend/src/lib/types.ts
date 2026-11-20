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
}

export interface Artifact {
	slot: number; set_name: string; rarity: number; level: number;
	main_stat: string; substats: string[]; icon: string;
}
export interface CharacterDetail extends Character {
	artifacts: Artifact[];
	stats: { name: string; value: string }[];
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
}
export interface Settings {
	connection: Connection;
	sync_interval_minutes: number;
	default_targets: Targets;
	level_caps: number[];
	gamedata: { fetched_at: string | null; last_error: string | null; count: number };
}
export interface Account { uid: number; server: string; nickname: string; level: number }
export type ConnectResponse = { status: 'connected'; uid: number } | { status: 'choose'; accounts: Account[] };
