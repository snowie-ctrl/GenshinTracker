/** Route every image through the backend cache. Game art arrives as a UI_ name, HoYoLAB icons as URLs. */
export function imgSrc(icon: string | null | undefined): string | null {
	if (!icon) return null;
	if (/^https?:\/\//.test(icon)) return `/api/img/remote?url=${encodeURIComponent(icon)}`;
	return `/api/img/${encodeURIComponent(icon)}`;
}

/** A safe CSS `url("...")` for a third-party URL: quotes, parens, backslashes and newlines cannot end the token. */
export function cssUrl(src: string): string {
	const safe = src.replace(/["'()\\\s]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, '0'));
	return `url("${safe}")`;
}
