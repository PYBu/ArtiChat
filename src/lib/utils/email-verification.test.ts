import { describe, expect, it } from 'vitest';

import {
	isEmailVerificationCodeComplete,
	normalizeEmailVerificationCode
} from './email-verification';

describe('email verification code input', () => {
	it('normalizes pasted separators and full-width digits', () => {
		expect(normalizeEmailVerificationCode('１２３ ４５６')).toBe('123456');
		expect(normalizeEmailVerificationCode('123-456')).toBe('123456');
	});

	it('keeps at most six digits and validates the normalized value', () => {
		expect(normalizeEmailVerificationCode('123456789')).toBe('123456');
		expect(isEmailVerificationCodeComplete('１２３ ４５６')).toBe(true);
		expect(isEmailVerificationCodeComplete('12345')).toBe(false);
	});
});
