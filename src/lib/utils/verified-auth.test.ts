import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('verified auth frontend contract', () => {
	it('supports registration verification and email-code login without replacing password login', () => {
		const api = readFileSync(resolve('src/lib/apis/auths/index.ts'), 'utf8');
		const page = readFileSync(resolve('src/routes/auth/+page.svelte'), 'utf8');
		const modal = readFileSync(resolve('src/lib/components/common/Modal.svelte'), 'utf8');
		const emailCodeModal = readFileSync(
			resolve('src/lib/components/common/EmailCodeModal.svelte'),
			'utf8'
		);
		const sensitiveActionPages = [
			'src/lib/components/chat/Settings/Account/UpdatePassword.svelte',
			'src/lib/components/chat/Settings/Account/BillingAddress.svelte',
			'src/lib/components/chat/Settings/Account/UpdateEmail.svelte'
		].map((path) => readFileSync(resolve(path), 'utf8'));

		expect(api).toContain('userEmailCodeSignIn');
		expect(api).toContain('verification_token');
		expect(page).toContain("mode === 'email-code'");
		expect(page).toContain('requestEmailChallenge');
		expect(page).toContain('verifyEmailChallenge');
		expect(page).toContain('userSignIn(email, password)');
		expect(page).toContain('<EmailCodeModal');
		expect(page).not.toContain('pattern="[0-9]{6}"');
		expect(modal).toContain('export let closeOnBackdrop = true');
		expect(modal).toContain('export let closeOnEscape = true');
		expect(emailCodeModal).toContain("import XMark from '$lib/components/icons/XMark.svelte'");
		expect(emailCodeModal).toContain('closeOnBackdrop={false}');
		expect(emailCodeModal).toContain('closeOnEscape={false}');
		for (const sensitiveActionPage of sensitiveActionPages) {
			expect(sensitiveActionPage).toContain('<EmailCodeModal');
			expect(sensitiveActionPage).not.toContain('pattern="[0-9]{6}"');
		}
	});
});
