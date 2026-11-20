import { api, errorMessage } from './api';
import type { Connection, SyncStatus } from './types';

class SyncStore {
	status = $state<SyncStatus | null>(null);
	connection = $state<Connection | null>(null);
	error = $state<string | null>(null);
	/** Increments whenever a sync finishes; pages read it inside $effect to refetch. */
	version = $state(0);
	#timer: ReturnType<typeof setTimeout> | null = null;
	#awaitingFinish = false;

	async loadConnection(): Promise<void> {
		try {
			this.connection = (await api.settings()).connection;
		} catch {
			/* nav still works without it */
		}
	}

	async start(trigger: 'auto' | 'manual'): Promise<void> {
		try {
			const r = await api.startSync(trigger);
			this.error = null;
			if (r.started || r.reason === 'joined') this.#awaitingFinish = true;
		} catch (e) {
			this.error = errorMessage(e);
		}
		await this.poll();
	}

	async poll(): Promise<void> {
		if (this.#timer) {
			clearTimeout(this.#timer);
			this.#timer = null;
		}
		const wasRunning = this.status?.running ?? false;
		try {
			this.status = await api.syncStatus();
		} catch (e) {
			this.error = errorMessage(e);
			return;
		}
		if (this.status.running) {
			this.#timer = setTimeout(() => this.poll(), 2000);
		} else if (wasRunning || this.#awaitingFinish) {
			this.#awaitingFinish = false;
			this.version += 1;
			await this.loadConnection();
		}
	}
}

export const sync = new SyncStore();
