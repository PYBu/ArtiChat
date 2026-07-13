import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('email admin routes', () => {
	it('keeps email settings, templates, and deliveries as independent pages', () => {
		expect(existsSync(resolve('src/routes/(app)/admin/registration/+page.svelte'))).toBe(true);
		for (const page of ['settings', 'templates', 'deliveries']) {
			expect(
				existsSync(resolve(`src/routes/(app)/admin/email/${page}/+page.svelte`)),
				`${page} page should exist`
			).toBe(true);
		}

		const layout = readFileSync(resolve('src/routes/(app)/admin/+layout.svelte'), 'utf8');
		expect(layout).toContain('/admin/email');

		const shell = readFileSync(
			resolve('src/lib/components/admin/Email/EmailPageShell.svelte'),
			'utf8'
		);
		expect(shell).toContain('/admin/email/settings');
		expect(shell).toContain('/admin/email/templates');
		expect(shell).toContain('/admin/email/deliveries');
		expect(shell).toContain('<select');
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
