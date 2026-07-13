import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('pending gift sidebar entry', () => {
	it('shows an unnumbered gift action above the expanded user menu', () => {
		const sidebar = readFileSync(resolve('src/lib/components/layout/Sidebar.svelte'), 'utf8');

		expect(sidebar).toContain('getPendingGiftCards');
		expect(sidebar).toContain('可领取的礼品');
		expect(sidebar).toContain("showSettings.set('redeem_code')");
		expect(sidebar).not.toMatch(/可领取的礼品\s*[（(]\s*\{/);

		const giftEntry = sidebar.indexOf('id="pending-gift-entry"');
		const expandedUserMenu = sidebar.indexOf('className="w-[calc(var(--sidebar-width)-1rem)]"');
		expect(giftEntry).toBeGreaterThan(-1);
		expect(giftEntry).toBeLessThan(expandedUserMenu);
	});

	it('refreshes the gift action after a subscription change', () => {
		const sidebar = readFileSync(resolve('src/lib/components/layout/Sidebar.svelte'), 'utf8');

		expect(sidebar).toContain('subscriptionRefreshTick');
		expect(sidebar).toMatch(/subscriptionRefreshTick\.subscribe\(\(\)\s*=>\s*\{\s*loadPendingGiftCards\(\);/);
	});
});
