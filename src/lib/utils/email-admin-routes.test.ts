import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('email admin routes', () => {
	it('consolidates registration and email under settings while preserving redirects', () => {
		expect(existsSync(resolve('src/routes/(app)/admin/registration/+page.svelte'))).toBe(true);
		for (const page of ['', 'settings', 'templates', 'deliveries']) {
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

		const layout = readFileSync(resolve('src/routes/(app)/admin/+layout.svelte'), 'utf8');
		expect(layout).not.toContain('/admin/email');
		expect(layout).not.toContain('/admin/registration');

		const settings = readFileSync(
			resolve('src/lib/components/admin/Settings/Email.svelte'),
			'utf8'
		);
		expect(settings).toContain('RegistrationSettings');
		expect(settings).toContain('EmailSettings');
		expect(settings).toContain('EmailTemplates');
		expect(settings).toContain('EmailDeliveries');
		expect(settings).toContain('启用邮箱功能');
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
