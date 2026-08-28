import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';

export type AccessRestrictionConfig = {
	enabled: boolean;
	geoip: { provider: string; available: boolean; updated_at: number | null };
	geoip_failure_mode: string;
	retention_days: number;
};

export type IPRule = {
	id: string;
	network: string;
	enabled: boolean;
	note: string | null;
	created_by: string;
	created_at: number;
	updated_at: number;
};

export type RegionRule = {
	id: string;
	country_code: string;
	enabled: boolean;
	note: string | null;
	created_by: string;
	created_at: number;
	updated_at: number;
};

export type LoginEvent = {
	id: string;
	user_id: string | null;
	user_email: string | null;
	user_name: string | null;
	ip_address: string | null;
	country_code: string | null;
	auth_method: string;
	result: string;
	reason: string | null;
	rule_id: string | null;
	user_agent: string | null;
	created_at: number;
};

const endpoint = `${WEBUI_API_BASE_URL}/access-restrictions`;

export const getAccessRestrictionConfig = (token: string) =>
	apiJsonFetch<AccessRestrictionConfig>(`${endpoint}/config`, token);

export const updateAccessRestrictionConfig = (token: string, enabled: boolean) =>
	apiJsonFetch<AccessRestrictionConfig>(`${endpoint}/config`, token, {
		method: 'PUT',
		body: JSON.stringify({ enabled })
	});

export const getAccessRestrictionIPRules = (token: string) =>
	apiJsonFetch<{ items: IPRule[] }>(`${endpoint}/ip-rules`, token);

export const createAccessRestrictionIPRule = (
	token: string,
	payload: Pick<IPRule, 'network' | 'note' | 'enabled'>
) =>
	apiJsonFetch<IPRule>(`${endpoint}/ip-rules`, token, {
		method: 'POST',
		body: JSON.stringify(payload)
	});

export const updateAccessRestrictionIPRule = (
	token: string,
	id: string,
	payload: Partial<Pick<IPRule, 'note' | 'enabled'>>
) =>
	apiJsonFetch<IPRule>(`${endpoint}/ip-rules/${encodeURIComponent(id)}`, token, {
		method: 'PATCH',
		body: JSON.stringify(payload)
	});

export const deleteAccessRestrictionIPRule = (token: string, id: string) =>
	apiJsonFetch<{ status: boolean }>(`${endpoint}/ip-rules/${encodeURIComponent(id)}`, token, {
		method: 'DELETE'
	});

export const getAccessRestrictionRegions = (token: string) =>
	apiJsonFetch<{ items: RegionRule[] }>(`${endpoint}/regions`, token);

export const createAccessRestrictionRegion = (
	token: string,
	payload: Pick<RegionRule, 'country_code' | 'note' | 'enabled'>
) =>
	apiJsonFetch<RegionRule>(`${endpoint}/regions`, token, {
		method: 'POST',
		body: JSON.stringify(payload)
	});

export const updateAccessRestrictionRegion = (
	token: string,
	id: string,
	payload: Partial<Pick<RegionRule, 'note' | 'enabled'>>
) =>
	apiJsonFetch<RegionRule>(`${endpoint}/regions/${encodeURIComponent(id)}`, token, {
		method: 'PATCH',
		body: JSON.stringify(payload)
	});

export const deleteAccessRestrictionRegion = (token: string, id: string) =>
	apiJsonFetch<{ status: boolean }>(`${endpoint}/regions/${encodeURIComponent(id)}`, token, {
		method: 'DELETE'
	});

export const getAccessRestrictionLoginRecords = (
	token: string,
	filters: { query?: string; result?: string; limit?: number; offset?: number } = {}
) => {
	const params = new URLSearchParams();
	if (filters.query) params.set('query', filters.query);
	if (filters.result) params.set('result', filters.result);
	if (filters.limit !== undefined) params.set('limit', String(filters.limit));
	if (filters.offset !== undefined) params.set('offset', String(filters.offset));
	const suffix = params.toString() ? `?${params.toString()}` : '';
	return apiJsonFetch<{ items: LoginEvent[]; total_item_count: number }>(
		`${endpoint}/login-records${suffix}`,
		token
	);
};
