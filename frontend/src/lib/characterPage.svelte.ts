import { getContext, setContext } from 'svelte';
import { api, errorMessage } from './api';
import type { CharacterDetail, GoalBody, Goal, Kit, KitResponse, Targets } from './types';

const KEY = Symbol('character-page');

/** Data shared by the character layout and its Current / Build / Guide tabs. */
export class CharacterPage {
	slug = $state('');
	c = $state<CharacterDetail | null>(null);
	kit = $state<Kit | null>(null);
	kitState = $state<KitResponse['state'] | 'loading'>('loading');
	caps = $state<number[]>([20, 40, 50, 60, 70, 80, 90]);
	error = $state<string | null>(null);
	saveError = $state<string | null>(null);

	async load(slug: string): Promise<void> {
		this.slug = slug;
		try {
			const [detail, settings] = await Promise.all([api.character(slug), api.settings()]);
			if (this.slug !== slug) return;            // a newer character was opened meanwhile
			this.c = detail;
			this.caps = settings.level_caps;
			this.error = null;
		} catch (e) {
			if (this.slug === slug) this.error = errorMessage(e);
		}
	}

	async loadKit(slug: string): Promise<void> {
		this.kit = null;
		this.kitState = 'loading';
		try {
			const res = await api.characterKit(slug);
			if (this.slug !== slug) return;
			this.kit = res.kit;
			this.kitState = res.state;
		} catch {
			if (this.slug === slug) {
				this.kit = null;
				this.kitState = 'unavailable';
			}
		}
	}

	async saveGoal(body: GoalBody): Promise<void> {
		if (!this.c) return;
		try {
			await api.setGoal(this.c.id, body);
			this.saveError = null;
		} catch (e) {
			this.saveError = errorMessage(e);
		}
		await this.load(this.slug);
	}
}

export function setCharacterPage(p: CharacterPage): void {
	setContext(KEY, p);
}

export function getCharacterPage(): CharacterPage {
	return getContext<CharacterPage>(KEY);
}
