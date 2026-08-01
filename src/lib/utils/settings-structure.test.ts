import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const read = (path: string) => readFileSync(resolve(path), 'utf8');

describe('settings structure', () => {
	it('keeps platform and update pages on the official settings grammar', () => {
		const platform = read('src/lib/components/admin/Settings/Platform.svelte');
		const update = read('src/lib/components/admin/Settings/Update.svelte');
		const versionPanel = read('src/lib/components/admin/Settings/VersionUpdatePanel.svelte');

		for (const source of [platform, update]) {
			for (const marker of ['AdminSettingSection', 'AdminSettingRow', 'AdminSettingField']) {
				expect(source).toContain(marker);
			}
			expect(source).not.toContain('admin-settings-surface');
		}

		expect(versionPanel).toContain('AdminSettingRow');
		expect(versionPanel).toContain('AdminSettingField');
		expect(versionPanel).not.toContain('overflow-hidden rounded-lg border border-gray-200');
		expect(update).toContain('/admin/subscriptions/announcements');
	});

	it('renders the account billing form through AccountSecurity only', () => {
		const account = read('src/lib/components/chat/Settings/Account.svelte');
		const accountSecurity = read('src/lib/components/chat/Settings/Account/AccountSecurity.svelte');

		expect(account).not.toMatch(/<BillingAddress\b/);
		expect(account).toContain('<AccountSecurity />');
		expect(accountSecurity.match(/<BillingAddress\s*\/>/g)).toHaveLength(1);
	});
});
