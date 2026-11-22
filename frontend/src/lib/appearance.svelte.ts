import { api } from './api';

type Loader = () => Promise<{ background_animated: boolean }>;
type Saver = (on: boolean) => Promise<unknown>;

export class AppearanceStore {
	backgroundAnimated = $state(true);
	#load: Loader;
	#save: Saver;

	constructor(load: Loader, save: Saver) {
		this.#load = load;
		this.#save = save;
	}

	async load(): Promise<void> {
		try {
			this.backgroundAnimated = (await this.#load()).background_animated;
		} catch {
			/* keep the default: animated */
		}
	}

	async setBackgroundAnimated(on: boolean): Promise<void> {
		const before = this.backgroundAnimated;
		this.backgroundAnimated = on;
		try {
			await this.#save(on);
		} catch (e) {
			this.backgroundAnimated = before;
			throw e;
		}
	}
}

export function createAppearance(load: Loader, save: Saver): AppearanceStore {
	return new AppearanceStore(load, save);
}

export const appearance = createAppearance(
	() => api.settings(),
	(on) => api.saveSettings({ background_animated: on })
);
