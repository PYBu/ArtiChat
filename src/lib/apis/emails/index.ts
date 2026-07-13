import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';

export type EmailSettings = {
	enabled: boolean;
	host: string;
	port: number;
	username: string;
	password: string;
	password_configured: boolean;
	security: 'none' | 'starttls' | 'ssl';
	sender_email: string;
	sender_name: string;
	reply_to: string;
	public_url: string;
	subscription_notifications: boolean;
};

export type EmailTemplate = {
	key: string;
	subject: string;
	markdown_body: string;
	html_body: string;
	is_enabled: boolean;
	updated_at: number;
	allowed_variables: string[];
};

export type EmailTemplatePreview = {
	subject: string;
	html_body: string;
	text_body: string;
};

export type EmailDelivery = {
	id: string;
	template_key: string;
	recipient: string;
	subject: string;
	status: 'pending' | 'sending' | 'sent' | 'failed';
	error: string | null;
	attempts: number;
	last_attempt_at: number | null;
	sent_at: number | null;
	created_at: number;
};

export type RegistrationSettings = {
	allowed_domains: string[];
	allow_subdomains: boolean;
	verification_enabled: boolean;
	email_code_login_enabled: boolean;
	sensitive_action_verification_enabled: boolean;
};

export type SensitiveAction = 'password' | 'billing_address' | 'email';

export const getEmailSettings = async (token: string) => {
	return apiJsonFetch<EmailSettings>(`${WEBUI_API_BASE_URL}/emails/admin/settings`, token);
};

export const updateEmailSettings = async (token: string, settings: Partial<EmailSettings>) => {
	return apiJsonFetch<EmailSettings>(`${WEBUI_API_BASE_URL}/emails/admin/settings`, token, {
		method: 'PUT',
		body: JSON.stringify(settings)
	});
};

export const testEmailConnection = async (token: string) => {
	return apiJsonFetch<{ ok: boolean; stage: string }>(
		`${WEBUI_API_BASE_URL}/emails/admin/connection-test`,
		token,
		{ method: 'POST' }
	);
};

export const sendEmailTest = async (token: string, recipient: string) => {
	return apiJsonFetch<EmailDelivery>(`${WEBUI_API_BASE_URL}/emails/admin/test-email`, token, {
		method: 'POST',
		body: JSON.stringify({ recipient })
	});
};

export const getEmailTemplates = async (token: string) => {
	return apiJsonFetch<EmailTemplate[]>(`${WEBUI_API_BASE_URL}/emails/admin/templates`, token);
};

export const updateEmailTemplate = async (
	token: string,
	templateKey: string,
	template: Pick<EmailTemplate, 'subject' | 'html_body' | 'is_enabled'>
) => {
	return apiJsonFetch<EmailTemplate>(
		`${WEBUI_API_BASE_URL}/emails/admin/templates/${encodeURIComponent(templateKey)}`,
		token,
		{ method: 'PUT', body: JSON.stringify(template) }
	);
};

export const previewEmailTemplate = async (
	token: string,
	templateKey: string,
	template: Pick<EmailTemplate, 'subject' | 'html_body' | 'is_enabled'>,
	signal?: AbortSignal
) => {
	return apiJsonFetch<EmailTemplatePreview>(
		`${WEBUI_API_BASE_URL}/emails/admin/templates/${encodeURIComponent(templateKey)}/preview`,
		token,
		{ method: 'POST', body: JSON.stringify(template), signal }
	);
};

export const getEmailDeliveries = async (
	token: string,
	options: { limit?: number; offset?: number } = {}
) => {
	const params = new URLSearchParams();
	if (options.limit !== undefined) params.set('limit', String(options.limit));
	if (options.offset !== undefined) params.set('offset', String(options.offset));
	const query = params.toString();
	return apiJsonFetch<EmailDelivery[]>(
		`${WEBUI_API_BASE_URL}/emails/admin/deliveries${query ? `?${query}` : ''}`,
		token
	);
};

export const retryEmailDelivery = async (token: string, deliveryId: string) => {
	return apiJsonFetch<EmailDelivery>(
		`${WEBUI_API_BASE_URL}/emails/admin/deliveries/${encodeURIComponent(deliveryId)}/retry`,
		token,
		{ method: 'POST' }
	);
};

export const getRegistrationSettings = async (token: string) => {
	return apiJsonFetch<RegistrationSettings>(
		`${WEBUI_API_BASE_URL}/emails/admin/registration`,
		token
	);
};

export const updateRegistrationSettings = async (
	token: string,
	settings: Partial<RegistrationSettings>
) => {
	return apiJsonFetch<RegistrationSettings>(
		`${WEBUI_API_BASE_URL}/emails/admin/registration`,
		token,
		{
			method: 'PUT',
			body: JSON.stringify(settings)
		}
	);
};

export const getPublicRegistrationSettings = async () => {
	return apiJsonFetch<{
		verification_enabled: boolean;
		email_code_login_enabled: boolean;
	}>(`${WEBUI_API_BASE_URL}/emails/registration/public`, null);
};

export const requestEmailChallenge = async (email: string, purpose: 'registration' | 'login') => {
	return apiJsonFetch<{ status: boolean }>(
		`${WEBUI_API_BASE_URL}/emails/challenges/request`,
		null,
		{
			method: 'POST',
			body: JSON.stringify({ email, purpose })
		}
	);
};

export const verifyEmailChallenge = async (
	email: string,
	purpose: 'registration' | 'login',
	code: string
) => {
	return apiJsonFetch<{ verification_token: string }>(
		`${WEBUI_API_BASE_URL}/emails/challenges/verify`,
		null,
		{ method: 'POST', body: JSON.stringify({ email, purpose, code }) }
	);
};

export const forgotPassword = async (email: string) => {
	return apiJsonFetch<{ status: boolean }>(`${WEBUI_API_BASE_URL}/emails/password/forgot`, null, {
		method: 'POST',
		body: JSON.stringify({ email })
	});
};

export const resetPassword = async (token: string, newPassword: string) => {
	return apiJsonFetch<{ status: boolean }>(`${WEBUI_API_BASE_URL}/emails/password/reset`, null, {
		method: 'POST',
		body: JSON.stringify({ token, new_password: newPassword })
	});
};

export const requestSensitiveChallenge = async (token: string, action: SensitiveAction) => {
	return apiJsonFetch<{ status: boolean; verification_required: boolean }>(
		`${WEBUI_API_BASE_URL}/emails/challenges/sensitive/request`,
		token,
		{ method: 'POST', body: JSON.stringify({ action }) }
	);
};

export const verifySensitiveChallenge = async (
	token: string,
	action: SensitiveAction,
	code: string
) => {
	return apiJsonFetch<{ verification_token: string }>(
		`${WEBUI_API_BASE_URL}/emails/challenges/sensitive/verify`,
		token,
		{ method: 'POST', body: JSON.stringify({ action, code }) }
	);
};

export const requestNewEmailChallenge = async (
	token: string,
	email: string,
	currentVerificationToken: string
) => {
	return apiJsonFetch<{ status: boolean; verification_required: boolean }>(
		`${WEBUI_API_BASE_URL}/emails/challenges/sensitive/email/request-new`,
		token,
		{
			method: 'POST',
			body: JSON.stringify({ email, current_verification_token: currentVerificationToken })
		}
	);
};

export const verifyNewEmailChallenge = async (token: string, email: string, code: string) => {
	return apiJsonFetch<{ verification_token: string }>(
		`${WEBUI_API_BASE_URL}/emails/challenges/sensitive/email/verify-new`,
		token,
		{ method: 'POST', body: JSON.stringify({ email, code }) }
	);
};
