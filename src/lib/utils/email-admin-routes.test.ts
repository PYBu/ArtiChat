import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('email admin routes', () => {
	it('consolidates registration and email in admin settings', () => {
		expect(existsSync(resolve('src/routes/(app)/admin/registration/+page.svelte'))).toBe(true);
		const emailPage = readFileSync(resolve('src/routes/(app)/admin/email/+page.svelte'), 'utf8');
		expect(emailPage).toContain('/admin/settings/email');

		for (const page of ['settings', 'templates', 'deliveries']) {
			const route = page ? `${page}/` : '';
			expect(
				existsSync(resolve(`src/routes/(app)/admin/email/${route}+page.svelte`)),
				`${page || 'email'} redirect page should exist`
			).toBe(true);
			const redirect = readFileSync(
				resolve(`src/routes/(app)/admin/email/${route}+page.svelte`),
				'utf8'
			);
			expect(redirect).toContain('/admin/settings/email');
		}

		const settings = readFileSync(
			resolve('src/lib/components/admin/Settings/Email.svelte'),
			'utf8'
		);
		expect(settings).toContain('RegistrationSettings');
		expect(settings).toContain('EmailSettings');
		expect(settings).toContain('EmailTemplates');
		expect(settings).toContain('EmailDeliveries');
		expect(settings).toContain('启用邮箱功能');
		expect(settings).toContain('AdminSettingSection');
		expect(settings).toContain('AdminSettingRow');
		expect(settings).not.toContain('admin-settings-surface');

		for (const [file, markers] of [
			[
				'src/lib/components/admin/Registration/RegistrationSettings.svelte',
				['AdminSettingSection', 'AdminSettingField', 'AdminSettingRow']
			],
			[
				'src/lib/components/admin/Email/EmailSettings.svelte',
				['AdminSettingSection', 'AdminSettingField', 'AdminSettingRow']
			],
			[
				'src/lib/components/admin/Email/EmailTemplates.svelte',
				['AdminSettingSection', 'AdminSettingField', 'AdminSettingRow']
			],
			[
				'src/lib/components/admin/Email/EmailDeliveries.svelte',
				['AdminSettingSection', 'AdminSettingRow']
			]
		] as const) {
			const component = readFileSync(resolve(file), 'utf8');
			for (const marker of markers) expect(component).toContain(marker);
			expect(component).not.toContain('admin-settings-surface');
		}

		const adminSettings = readFileSync(resolve('src/lib/components/admin/Settings.svelte'), 'utf8');
		expect(adminSettings).toContain("import Email from './Settings/Email.svelte'");
		expect(adminSettings).toContain("id: 'email'");
		expect(adminSettings).toContain("selectedTab === 'email'");
	});

	it('does not offer retry for expired security credentials', () => {
		const deliveries = readFileSync(
			resolve('src/lib/components/admin/Email/EmailDeliveries.svelte'),
			'utf8'
		);

		for (const template of [
			'registration_code',
			'login_code',
			'sensitive_action_code',
			'password_reset'
		]) {
			expect(deliveries).toContain(template);
		}
		expect(deliveries).toContain('!nonRetryableTemplates.has(delivery.template_key)');
	});
});
