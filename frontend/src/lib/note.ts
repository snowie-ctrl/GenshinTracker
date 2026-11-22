/** A status note next to a Save button: "Saved." fades after `ms`; errors stay until the next save. */
export function noteTimer(set: (v: string | null) => void, ms = 3000) {
	let timer: ReturnType<typeof setTimeout> | undefined;
	return {
		saved(message = 'Saved.') {
			clearTimeout(timer);
			set(message);
			timer = setTimeout(() => set(null), ms);
		},
		error(message: string) {
			clearTimeout(timer);
			set(message);
		},
		/** Drop a pending clear (on unmount). */
		cancel() {
			clearTimeout(timer);
			timer = undefined;
		}
	};
}
