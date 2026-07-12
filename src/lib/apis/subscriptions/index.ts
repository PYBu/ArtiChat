import { WEBUI_API_BASE_URL } from '$lib/constants';

const jsonFetch = async (url: string, token: string, options: RequestInit = {}) => {
	let error = null;
	const headers = Object.assign(
		{
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		options.headers ?? {}
	);
	const request = Object.assign({}, options, { headers });
	const res = await fetch(url, request)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			return null;
		});

	if (error) throw error;
	return res;
};

export const getMySubscription = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/me`, token);
};

export const getSubscriptionPlans = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/plans`, token);
};

export const getMySubscriptionUsage = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/usage`, token);
};

export const redeemSubscriptionCode = async (token: string, code: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/redeem`, token, {
		method: 'POST',
		body: JSON.stringify({ code })
	});
};

export const getMySubscriptionRecords = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/records`, token);
};

export const getPendingGiftCards = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/gift-cards/pending`, token);
};

export const claimGiftCard = async (token: string, grantId: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/gift-cards/${encodeURIComponent(grantId)}/claim`, token, {
		method: 'POST'
	});
};

export const updateBillingAddress = async (
	token: string,
	billingAddress: Record<string, unknown>,
	verificationToken: string | null = null
) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/billing-address`, token, {
		method: 'PUT',
		body: JSON.stringify({ billing_address: billingAddress, verification_token: verificationToken })
	});
};

export const getAdminSubscriptionPlans = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/plans`, token);
};

export const updateAdminSubscriptionPlan = async (token: string, planId: string, payload: Record<string, unknown>) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/plans/${encodeURIComponent(planId)}`, token, {
		method: 'PATCH',
		body: JSON.stringify(payload)
	});
};

export const getAdminSubscriptionModels = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/models`, token);
};

export const updateAdminModelSubscriptionPolicies = async (
	token: string,
	models: Array<{ id: string; subscription: Record<string, unknown> }>
) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/models/bulk`, token, {
		method: 'PUT',
		body: JSON.stringify({ models })
	});
};

export const updateAdminModelSubscriptionPolicy = async (
	token: string,
	modelId: string,
	subscription: Record<string, unknown>
) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/models/${encodeURIComponent(modelId)}`, token, {
		method: 'PUT',
		body: JSON.stringify({ subscription })
	});
};

export const getAdminRedemptionCodes = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/codes`, token);
};

export const createAdminRedemptionCodes = async (token: string, payload: Record<string, unknown>) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/codes`, token, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const deleteAdminRedemptionCode = async (token: string, codeId: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/codes/${encodeURIComponent(codeId)}`, token, {
		method: 'DELETE'
	});
};

export const getAdminGiftCards = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/gift-cards`, token);
};

export const createAdminGiftCards = async (token: string, payload: Record<string, unknown>) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/gift-cards`, token, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const revokeAdminGiftCard = async (token: string, grantId: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/gift-cards/${encodeURIComponent(grantId)}`, token, {
		method: 'DELETE'
	});
};

export const getAdminUserSubscriptions = async (token: string, query = '') => {
	const params = new URLSearchParams();
	if (query) params.set('query', query);
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/users?${params.toString()}`, token);
};

export const updateAdminUserSubscription = async (
	token: string,
	userId: string,
	payload: Record<string, unknown>
) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/users/${encodeURIComponent(userId)}`, token, {
		method: 'PATCH',
		body: JSON.stringify(payload)
	});
};

export const getAdminSubscriptionUsage = async (
	token: string,
	filters: {
		userId?: string;
		modelId?: string;
		status?: string;
		startAt?: number;
		endAt?: number;
		limit?: number;
		offset?: number;
	} = {}
) => {
	const params = new URLSearchParams();
	if (filters.userId) params.set('user_id', filters.userId);
	if (filters.modelId) params.set('model_id', filters.modelId);
	if (filters.status) params.set('status', filters.status);
	if (filters.startAt !== undefined) params.set('start_at', String(filters.startAt));
	if (filters.endAt !== undefined) params.set('end_at', String(filters.endAt));
	if (filters.limit !== undefined) params.set('limit', String(filters.limit));
	if (filters.offset !== undefined) params.set('offset', String(filters.offset));
	const query = params.toString();
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/usage${query ? `?${query}` : ''}`, token);
};

export const getAdminSubscriptionLedger = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/ledger`, token);
};
