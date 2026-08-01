import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('pending gift entry', () => {
	it('is mounted by the production sidebar', () => {
		const entry = readFileSync(
			resolve('src/lib/components/layout/Sidebar/PendingGiftEntry.svelte'),
			'utf8'
		);

		expect(entry).toContain('getPendingGiftCards');
		expect(entry).toContain('id="pending-gift-entry"');
		expect(entry).toContain("dispatch('redeem')");
		expect(entry).toContain('w-full');
		expect(entry).not.toContain('w-fit');

		const sidebar = readFileSync(resolve('src/lib/components/layout/Sidebar.svelte'), 'utf8');
		expect(sidebar).toContain("import PendingGiftEntry from './Sidebar/PendingGiftEntry.svelte'");
		expect(sidebar).toContain('<PendingGiftEntry');
		expect(sidebar).toContain("showSettings.set('redeem_code')");
	});

	it('refreshes the gift action after a subscription change', () => {
		const entry = readFileSync(
			resolve('src/lib/components/layout/Sidebar/PendingGiftEntry.svelte'),
			'utf8'
		);

		expect(entry).toContain('subscriptionRefreshTick');
		expect(entry).toContain('subscriptionRefreshTick.subscribe');
	});
});
