import { WEBUI_API_BASE_URL } from '$lib/constants';

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
	is_enabled: boolean;
	updated_at: number;
	allowed_variables: string[];
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

const jsonFetch = async <T>(url: string, token: string, options: RequestInit = {}): Promise<T> => {
	let error: unknown = null;
	const headers = Object.assign(
		{
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		options.headers ?? {}
	);
	const response = await fetch(url, { ...options, headers })
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((reason) => {
			error = reason?.detail?.code ?? reason?.detail ?? reason;
			return null;
		});

	if (error) throw error;
	return response as T;
};

export const getEmailSettings = async (token: string) => {
	return jsonFetch<EmailSettings>(`${WEBUI_API_BASE_URL}/emails/admin/settings`, token);
};

export const updateEmailSettings = async (token: string, settings: Partial<EmailSettings>) => {
	return jsonFetch<EmailSettings>(`${WEBUI_API_BASE_URL}/emails/admin/settings`, token, {
		method: 'PUT',
		body: JSON.stringify(settings)
	});
};

export const testEmailConnection = async (token: string) => {
	return jsonFetch<{ ok: boolean; stage: string }>(
		`${WEBUI_API_BASE_URL}/emails/admin/connection-test`,
		token,
		{ method: 'POST' }
	);
};

export const sendEmailTest = async (token: string, recipient: string) => {
	return jsonFetch<EmailDelivery>(`${WEBUI_API_BASE_URL}/emails/admin/test-email`, token, {
		method: 'POST',
		body: JSON.stringify({ recipient })
	});
};

export const getEmailTemplates = async (token: string) => {
	return jsonFetch<EmailTemplate[]>(`${WEBUI_API_BASE_URL}/emails/admin/templates`, token);
};

export const updateEmailTemplate = async (
	token: string,
	templateKey: string,
	template: Pick<EmailTemplate, 'subject' | 'markdown_body' | 'is_enabled'>
) => {
	return jsonFetch<EmailTemplate>(
		`${WEBUI_API_BASE_URL}/emails/admin/templates/${encodeURIComponent(templateKey)}`,
		token,
		{ method: 'PUT', body: JSON.stringify(template) }
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
	return jsonFetch<EmailDelivery[]>(
		`${WEBUI_API_BASE_URL}/emails/admin/deliveries${query ? `?${query}` : ''}`,
		token
	);
};

export const retryEmailDelivery = async (token: string, deliveryId: string) => {
	return jsonFetch<EmailDelivery>(
		`${WEBUI_API_BASE_URL}/emails/admin/deliveries/${encodeURIComponent(deliveryId)}/retry`,
		token,
		{ method: 'POST' }
	);
};
