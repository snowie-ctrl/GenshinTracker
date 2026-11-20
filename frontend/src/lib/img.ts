/** Route every image through the backend cache. Game art arrives as a UI_ name, HoYoLAB icons as URLs. */
export function imgSrc(icon: string | null | undefined): string | null {
	if (!icon) return null;
	if (/^https?:\/\//.test(icon)) return `/api/img/remote?url=${encodeURIComponent(icon)}`;
	return `/api/img/${encodeURIComponent(icon)}`;
}
