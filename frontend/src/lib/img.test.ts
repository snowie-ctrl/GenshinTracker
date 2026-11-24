import { describe, expect, it } from 'vitest';
import { cssUrl } from './img';

describe('cssUrl', () => {
	it('wraps a plain url in a quoted url()', () => {
		expect(cssUrl('/api/img/remote?url=a')).toBe('url("/api/img/remote?url=a")');
	});
	it('cannot be broken out of by quotes, parens, backslashes or newlines', () => {
		const out = cssUrl('a"b\'c(d)e\\f\ng h');
		const inner = out.slice(5, -2);
		expect(out.startsWith('url("') && out.endsWith('")')).toBe(true);
		expect(inner).not.toMatch(/["'()\\\s]/);
		expect(inner).toBe('a%22b%27c%28d%29e%5Cf%0Ag%20h');
	});
});
