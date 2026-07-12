import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
	forgotPassword,
	getEmailDeliveries,
	getEmailSettings,
	getEmailTemplates,
	getRegistrationSettings,
	getPublicRegistrationSettings,
	requestEmailChallenge,
	requestNewEmailChallenge,
	requestSensitiveChallenge,
	resetPassword,
	retryEmailDelivery,
	sendEmailTest,
	testEmailConnection,
	updateEmailSettings,
	updateEmailTemplate,
	updateRegistrationSettings,
	verifyEmailChallenge,
	verifyNewEmailChallenge,
	verifySensitiveChallenge
} from './index';

describe('email admin api', () => {
	const fetchMock = vi.fn();

	beforeEach(() => {
		fetchMock.mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
		vi.stubGlobal('fetch', fetchMock);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		fetchMock.mockReset();
	});

	it('uses the independent settings, templates, and delivery endpoints', async () => {
		await getEmailSettings('token');
		await updateEmailSettings('token', { enabled: true });
		await testEmailConnection('token');
		await sendEmailTest('token', 'admin@example.com');
		await getEmailTemplates('token');
		await updateEmailTemplate('token', 'registration_code', {
			subject: 'Registration',
			markdown_body: '{{code}}',
			is_enabled: true
		});
		await getEmailDeliveries('token', { limit: 50, offset: 10 });
		await retryEmailDelivery('token', 'mail_1');
		await getRegistrationSettings('token');
		await updateRegistrationSettings('token', { allowed_domains: ['example.com'] });
		await getPublicRegistrationSettings();
		await requestEmailChallenge('alice@example.com', 'registration');
		await verifyEmailChallenge('alice@example.com', 'registration', '123456');
		await forgotPassword('alice@example.com');
		await resetPassword('reset-token', 'New-password-123!');
		await requestSensitiveChallenge('token', 'password');
		await verifySensitiveChallenge('token', 'password', '123456');
		await requestNewEmailChallenge('token', 'new@example.com', 'current-grant');
		await verifyNewEmailChallenge('token', 'new@example.com', '654321');

		expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
			expect.stringContaining('/emails/admin/settings'),
			expect.stringContaining('/emails/admin/settings'),
			expect.stringContaining('/emails/admin/connection-test'),
			expect.stringContaining('/emails/admin/test-email'),
			expect.stringContaining('/emails/admin/templates'),
			expect.stringContaining('/emails/admin/templates/registration_code'),
			expect.stringContaining('/emails/admin/deliveries?limit=50&offset=10'),
			expect.stringContaining('/emails/admin/deliveries/mail_1/retry'),
			expect.stringContaining('/emails/admin/registration'),
			expect.stringContaining('/emails/admin/registration'),
			expect.stringContaining('/emails/registration/public'),
			expect.stringContaining('/emails/challenges/request'),
			expect.stringContaining('/emails/challenges/verify'),
			expect.stringContaining('/emails/password/forgot'),
			expect.stringContaining('/emails/password/reset'),
			expect.stringContaining('/emails/challenges/sensitive/request'),
			expect.stringContaining('/emails/challenges/sensitive/verify'),
			expect.stringContaining('/emails/challenges/sensitive/email/request-new'),
			expect.stringContaining('/emails/challenges/sensitive/email/verify-new')
		]);
		expect(fetchMock.mock.calls[1][1]).toMatchObject({
			method: 'PUT',
			body: JSON.stringify({ enabled: true })
		});
		expect(fetchMock.mock.calls[2][1]).toMatchObject({ method: 'POST' });
		expect(fetchMock.mock.calls[3][1]).toMatchObject({
			method: 'POST',
			body: JSON.stringify({ recipient: 'admin@example.com' })
		});
	});
});
