import { describe, expect, it } from 'vitest';

import { emailErrorMessage } from './email-errors';

describe('email error messages', () => {
	it('turns security and configuration codes into actionable messages', () => {
		expect(emailErrorMessage('EMAIL_CODE_RESEND_COOLDOWN')).toContain('60');
		expect(emailErrorMessage('EMAIL_CODE_EXPIRED')).toContain('重新发送');
		expect(emailErrorMessage('EMAIL_CODE_ATTEMPTS_EXCEEDED')).toContain('重新发送');
		expect(emailErrorMessage('EMAIL_DELIVERY_DISABLED')).toContain('管理员');
		expect(emailErrorMessage('unknown')).toBe('unknown');
	});
});
