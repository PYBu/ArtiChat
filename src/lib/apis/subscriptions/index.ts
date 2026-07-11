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

export const updateBillingAddress = async (token: string, billingAddress: Record<string, unknown>) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/billing-address`, token, {
		method: 'PUT',
		body: JSON.stringify({ billing_address: billingAddress })
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

export const getAdminSubscriptionUsage = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/usage`, token);
};

export const getAdminSubscriptionLedger = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/subscriptions/admin/ledger`, token);
};
