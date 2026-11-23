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

	// A load that began before a toggle read an older value. It must not overwrite a toggle that saved
	// (#saved moved) or is still saving (#saving > 0); in the second case its value is kept as the
	// fallback should that save fail.
	#saved = 0;
	#saving = 0;
	#lateLoad: boolean | null = null;

	async load(): Promise<void> {
		const savedAtStart = this.#saved;
		try {
			const value = (await this.#load()).background_animated;
			if (this.#saved !== savedAtStart) return;
			if (this.#saving > 0) this.#lateLoad = value;
			else this.backgroundAnimated = value;
		} catch {
			/* keep the default: animated */
		}
	}

	async setBackgroundAnimated(on: boolean): Promise<void> {
		const before = this.backgroundAnimated;
		this.backgroundAnimated = on;
		this.#saving += 1;
		try {
			await this.#save(on);
			this.#saved += 1;
			this.#lateLoad = null;
		} catch (e) {
			this.backgroundAnimated = this.#lateLoad ?? before;
			this.#lateLoad = null;
			throw e;
		} finally {
			this.#saving -= 1;
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
