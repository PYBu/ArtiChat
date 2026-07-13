import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('verified auth frontend contract', () => {
	it('supports registration verification and email-code login without replacing password login', () => {
		const api = readFileSync(resolve('src/lib/apis/auths/index.ts'), 'utf8');
		const page = readFileSync(resolve('src/routes/auth/+page.svelte'), 'utf8');

		expect(api).toContain('userEmailCodeSignIn');
		expect(api).toContain('verification_token');
		expect(page).toContain("mode === 'email-code'");
		expect(page).toContain('requestEmailChallenge');
		expect(page).toContain('verifyEmailChallenge');
		expect(page).toContain('userSignIn(email, password)');
	});
});
