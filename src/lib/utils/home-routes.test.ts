import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('home navigation routes', () => {
	it('points the home tabs at their mounted routes', () => {
		const layout = readFileSync(resolve('src/routes/(app)/home/+layout.svelte'), 'utf8');

		expect(layout).toContain("$page.url.pathname.startsWith('/notes')");
		expect(layout).toContain('href="/notes"');
		expect(layout).toContain("$page.url.pathname.startsWith('/calendar')");
		expect(layout).toContain('href="/calendar"');
		expect(layout).not.toContain('/playground/notes');
		expect(layout).not.toContain('/playground/calendar');
		expect(layout).not.toContain('/playground/completions');
	});
});
