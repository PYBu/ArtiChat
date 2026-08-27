import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';

export type UserSummary = {
	id: string;
	email: string | null;
	username: string | null;
	name: string | null;
	created_at?: number | null;
};

export type SubscriptionFeatures = {
	icon?: string;
	subtitle?: string;
	highlights?: string[];
	model_summary?: string;
	cta_label?: string;
};

export type SubscriptionPlan = {
	id: string;
	display_name: string;
	tier_rank: number;
	period_days: number;
	plan_chatpoint_allowance_micros: number;
	description: string | null;
	features: SubscriptionFeatures | null;
	is_active: boolean;
	sort_order: number;
	created_at: number;
	updated_at: number;
};

export type UserSubscription = {
	id: string;
	user_id: string;
	tier: string;
	tier_rank: number;
	display_name: string;
	period_days: number;
	plan_chatpoint_allowance_micros: number;
	plan_balance_micros: number;
	check_balance_micros: number;
	starts_at: number;
	expires_at: number | null;
	period_start_at: number;
	period_end_at: number;
	next_reset_at: number;
	status: string;
	source: string;
	snapshot: Record<string, unknown> | null;
	billing_address: Record<string, unknown> | null;
	notes: string | null;
	created_at: number;
	updated_at: number;
};

export type SubscriptionModelPolicy = {
	allowed_tiers: string[];
	quota_mode: 'metered' | 'unlimited';
	usage_multiplier: string;
	input_chatpoint_per_million: string;
	output_chatpoint_per_million: string;
	cache_creation_chatpoint_per_million: string;
	cache_read_chatpoint_per_million: string;
};

export type AdminSubscriptionModel = {
	id: string;
	name: string | null;
	base_model_id: string | null;
	provider?: string | null;
	subscription: Partial<SubscriptionModelPolicy> | null;
};

export type RedemptionCode = {
	id: string;
	code: string | null;
	code_hash: string;
	code_preview: string;
	benefit_type: 'subscription' | 'recharge' | 'legacy';
	mode: 'single_use' | 'multi_use';
	max_uses: number;
	used_count: number;
	tier: string | null;
	duration_days: number | null;
	plan_chatpoint_micros: number;
	check_chatpoint_micros: number;
	expires_at: number | null;
	is_active: boolean;
	purged_at: number | null;
	batch_id: string | null;
	memo: string | null;
	created_by: string;
	created_at: number;
	updated_at: number;
};

export type GiftCardGrant = {
	id: string;
	redemption_code_id: string;
	user_id: string;
	status: 'pending' | 'claimed' | 'revoked';
	batch_id: string;
	claimed_at: number | null;
	memo: string | null;
	created_by: string;
	created_at: number;
	updated_at: number;
};

export type AdminGiftCard = {
	grant: GiftCardGrant;
	code: RedemptionCode | null;
	user: UserSummary | null;
};

export type SubscriptionUsage = {
	id: string;
	user_id?: string;
	user?: UserSummary | null;
	request_id?: string | null;
	usage_type?: 'chat' | 'image' | 'video' | string;
	media_unit?: 'image' | 'second' | string | null;
	media_units?: number | null;
	media_unit_price_micros?: number | null;
	model_id: string;
	tier: string;
	quota_mode: string;
	input_tokens: number;
	output_tokens: number;
	cache_creation_tokens: number | null;
	cache_read_tokens: number | null;
	total_tokens: number;
	cost_micros: number;
	plan_cost_micros: number;
	check_cost_micros: number;
	unpaid_cost_micros: number;
	first_token_latency_ms: number | null;
	total_duration_ms: number | null;
	client_ip?: string | null;
	status: string;
	created_at: number;
};

export type SubscriptionUsageSummary = {
	items: SubscriptionUsage[];
	total_item_count: number;
	total_cost_micros: number;
	total_input_tokens: number;
	total_output_tokens: number;
	total_cache_creation_tokens: number;
	total_cache_read_tokens: number;
	total_unpaid_cost_micros: number;
	total_plan_cost_micros: number;
	total_check_cost_micros: number;
	total_tokens: number;
	total_request_count: number;
	media_totals: Array<{
		usage_type: string;
		media_unit: string | null;
		units: number;
		cost_micros: number;
	}>;
	model_totals: Array<{
		model_id: string;
		total_tokens: number;
		request_count: number;
		cost_micros: number;
		plan_cost_micros: number;
		check_cost_micros: number;
		unpaid_cost_micros: number;
	}>;
};

export type SubscriptionUsageOverview = Omit<
	SubscriptionUsageSummary,
	'items' | 'total_item_count'
> & {
	generated_at: number;
	recent_30d_start_at: number;
	recent_30d_request_count: number;
};

export type SubscriptionLedgerEntry = {
	id: string;
	user_id: string;
	user?: UserSummary | null;
	event_type: string;
	tier_before: string | null;
	tier_after: string | null;
	plan_delta_micros: number;
	check_delta_micros: number;
	plan_balance_after_micros: number;
	check_balance_after_micros: number;
	reference_type: string | null;
	reference_id: string | null;
	metadata?: Record<string, unknown> | null;
	created_at: number;
};

export type AdminUsageFilters = {
	userId?: string;
	userEmail?: string;
	modelId?: string;
	status?: string;
	usageType?: 'chat' | 'image' | 'video' | string;
	mediaUnit?: 'image' | 'second' | string;
	startAt?: number;
	endAt?: number;
	limit?: number;
	offset?: number;
};

export type SubscriptionOverviewActivity = SubscriptionLedgerEntry & {
	user: UserSummary | null;
};

export type SubscriptionOverview = {
	generated_at: number;
	timezone: string;
	metrics: {
		active_subscriptions: {
			count: number;
			mtd_count: number;
			previous_mtd_count: number;
			mtd_change_percent: number | null;
		};
		pending_gifts: {
			count: number;
			batch_count: number;
		};
		daily_deductions: {
			plan_micros: number;
			check_micros: number;
			total_micros: number;
			request_count: number;
			day_start: number;
			day_end: number;
		};
		available_codes: {
			total: number;
			subscription: number;
			recharge: number;
			legacy: number;
		};
	};
	recent_activity: SubscriptionOverviewActivity[];
};

export type RedemptionResult = {
	subscription: UserSubscription;
	tier_before: string | null;
	tier_after: string | null;
	plan_delta_micros: number;
	check_delta_micros: number;
};

export type SubscriptionUsageResponse = {
	subscription: UserSubscription;
	usage: SubscriptionUsageSummary;
	ledger: SubscriptionLedgerEntry[];
};

export const getMySubscription = async (token: string) => {
	return apiJsonFetch<UserSubscription>(`${WEBUI_API_BASE_URL}/subscriptions/me`, token);
};

export const getSubscriptionPlans = async (token: string) => {
	return apiJsonFetch<SubscriptionPlan[]>(`${WEBUI_API_BASE_URL}/subscriptions/plans`, token);
};

export const getMySubscriptionUsage = async (token: string) => {
	return apiJsonFetch<SubscriptionUsageResponse>(
		`${WEBUI_API_BASE_URL}/subscriptions/usage`,
		token
	);
};

export const redeemSubscriptionCode = async (token: string, code: string) => {
	return apiJsonFetch<RedemptionResult>(`${WEBUI_API_BASE_URL}/subscriptions/redeem`, token, {
		method: 'POST',
		body: JSON.stringify({ code })
	});
};

export const getMySubscriptionRecords = async (token: string) => {
	return apiJsonFetch<{ ledger: SubscriptionLedgerEntry[] }>(
		`${WEBUI_API_BASE_URL}/subscriptions/records`,
		token
	);
};

export const getPendingGiftCards = async (token: string) => {
	return apiJsonFetch<{ items: GiftCardGrant[] }>(
		`${WEBUI_API_BASE_URL}/subscriptions/gift-cards/pending`,
		token
	);
};

export const claimGiftCard = async (token: string, grantId: string) => {
	return apiJsonFetch<RedemptionResult & { grant: GiftCardGrant }>(
		`${WEBUI_API_BASE_URL}/subscriptions/gift-cards/${encodeURIComponent(grantId)}/claim`,
		token,
		{ method: 'POST' }
	);
};

export const updateBillingAddress = async (
	token: string,
	billingAddress: Record<string, unknown>,
	verificationToken: string | null = null
) => {
	return apiJsonFetch<UserSubscription>(
		`${WEBUI_API_BASE_URL}/subscriptions/billing-address`,
		token,
		{
			method: 'PUT',
			body: JSON.stringify({
				billing_address: billingAddress,
				verification_token: verificationToken
			})
		}
	);
};

export const getAdminSubscriptionPlans = async (token: string) => {
	return apiJsonFetch<SubscriptionPlan[]>(`${WEBUI_API_BASE_URL}/subscriptions/admin/plans`, token);
};

export const getAdminSubscriptionOverview = async (token: string) => {
	return apiJsonFetch<SubscriptionOverview>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/overview`,
		token
	);
};

export const updateAdminSubscriptionPlan = async (
	token: string,
	planId: string,
	payload: Record<string, unknown>
) => {
	return apiJsonFetch<SubscriptionPlan>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/plans/${encodeURIComponent(planId)}`,
		token,
		{ method: 'PATCH', body: JSON.stringify(payload) }
	);
};

export const getAdminSubscriptionModels = async (token: string) => {
	return apiJsonFetch<AdminSubscriptionModel[]>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/models`,
		token
	);
};

export const updateAdminModelSubscriptionPolicies = async (
	token: string,
	models: Array<{ id: string; subscription: SubscriptionModelPolicy }>
) => {
	return apiJsonFetch<AdminSubscriptionModel[]>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/models/bulk`,
		token,
		{
			method: 'PUT',
			body: JSON.stringify({ models })
		}
	);
};

export const updateAdminModelSubscriptionPolicy = async (
	token: string,
	modelId: string,
	subscription: SubscriptionModelPolicy
) => {
	return apiJsonFetch<AdminSubscriptionModel>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/models/${encodeURIComponent(modelId)}`,
		token,
		{ method: 'PUT', body: JSON.stringify({ subscription }) }
	);
};

export const getAdminRedemptionCodes = async (
	token: string,
	status: 'available' | 'archive' | 'all' = 'available'
) => {
	const params = new URLSearchParams({ status });
	return apiJsonFetch<{ items: RedemptionCode[] }>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/codes?${params.toString()}`,
		token
	);
};

export const createAdminRedemptionCodes = async (
	token: string,
	payload: Record<string, unknown>
) => {
	return apiJsonFetch<{ raw_codes: string[]; code_ids: string[] }>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/codes`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(payload)
		}
	);
};

export const deleteAdminRedemptionCode = async (token: string, codeId: string) => {
	return apiJsonFetch<RedemptionCode>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/codes/${encodeURIComponent(codeId)}`,
		token,
		{ method: 'DELETE' }
	);
};

export const clearAdminRedemptionCodes = async (token: string, codeIds: string[]) => {
	return apiJsonFetch<{ items: RedemptionCode[] }>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/codes/clear`,
		token,
		{
			method: 'POST',
			body: JSON.stringify({ code_ids: codeIds })
		}
	);
};

export const getAdminGiftCards = async (token: string) => {
	return apiJsonFetch<{ items: AdminGiftCard[] }>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/gift-cards`,
		token
	);
};

export const createAdminGiftCards = async (token: string, payload: Record<string, unknown>) => {
	return apiJsonFetch<{ batch_id: string; grants: GiftCardGrant[]; raw_codes: string[] }>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/gift-cards`,
		token,
		{
			method: 'POST',
			body: JSON.stringify(payload)
		}
	);
};

export const revokeAdminGiftCard = async (token: string, grantId: string) => {
	return apiJsonFetch<GiftCardGrant>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/gift-cards/${encodeURIComponent(grantId)}`,
		token,
		{ method: 'DELETE' }
	);
};

export const getAdminUserSubscriptions = async (token: string, query = '') => {
	const params = new URLSearchParams();
	if (query) params.set('query', query);
	return apiJsonFetch<{
		items: Array<{ subscription: UserSubscription; user: UserSummary | null }>;
	}>(`${WEBUI_API_BASE_URL}/subscriptions/admin/users?${params.toString()}`, token);
};

export const updateAdminUserSubscription = async (
	token: string,
	userId: string,
	payload: Record<string, unknown>
) => {
	return apiJsonFetch<UserSubscription>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/users/${encodeURIComponent(userId)}`,
		token,
		{ method: 'PATCH', body: JSON.stringify(payload) }
	);
};

export const getAdminSubscriptionUsage = async (token: string, filters: AdminUsageFilters = {}) => {
	const params = new URLSearchParams();
	if (filters.userId) params.set('user_id', filters.userId);
	if (filters.userEmail) params.set('user_email', filters.userEmail);
	if (filters.modelId) params.set('model_id', filters.modelId);
	if (filters.status) params.set('status', filters.status);
	if (filters.usageType) params.set('usage_type', filters.usageType);
	if (filters.mediaUnit) params.set('media_unit', filters.mediaUnit);
	if (filters.startAt !== undefined) params.set('start_at', String(filters.startAt));
	if (filters.endAt !== undefined) params.set('end_at', String(filters.endAt));
	if (filters.limit !== undefined) params.set('limit', String(filters.limit));
	if (filters.offset !== undefined) params.set('offset', String(filters.offset));
	const query = params.toString();
	return apiJsonFetch<SubscriptionUsageSummary>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/usage${query ? `?${query}` : ''}`,
		token
	);
};

export const getAdminSubscriptionUsageOverview = async (token: string) => {
	return apiJsonFetch<SubscriptionUsageOverview>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/usage/overview`,
		token
	);
};

export const getAdminSubscriptionLedger = async (
	token: string,
	filters: Pick<AdminUsageFilters, 'userId' | 'startAt' | 'endAt' | 'limit' | 'offset'> & {
		eventType?: string;
	} = {}
) => {
	const params = new URLSearchParams();
	if (filters.userId) params.set('user_id', filters.userId);
	if (filters.eventType) params.set('event_type', filters.eventType);
	if (filters.startAt !== undefined) params.set('start_at', String(filters.startAt));
	if (filters.endAt !== undefined) params.set('end_at', String(filters.endAt));
	if (filters.limit !== undefined) params.set('limit', String(filters.limit));
	if (filters.offset !== undefined) params.set('offset', String(filters.offset));
	const query = params.toString();
	return apiJsonFetch<{ items: SubscriptionLedgerEntry[]; total_item_count: number }>(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/ledger${query ? `?${query}` : ''}`,
		token
	);
};

export const exportAdminSubscriptionUsage = async (
	token: string,
	kind: 'requests' | 'balances',
	filters: AdminUsageFilters = {}
) => {
	const params = new URLSearchParams({ kind });
	if (filters.userId) params.set('user_id', filters.userId);
	if (filters.modelId && kind === 'requests') params.set('model_id', filters.modelId);
	if (filters.status && kind === 'requests') params.set('status', filters.status);
	if (filters.usageType && kind === 'requests') params.set('usage_type', filters.usageType);
	if (filters.mediaUnit && kind === 'requests') params.set('media_unit', filters.mediaUnit);
	if (filters.startAt !== undefined) params.set('start_at', String(filters.startAt));
	if (filters.endAt !== undefined) params.set('end_at', String(filters.endAt));
	const response = await fetch(
		`${WEBUI_API_BASE_URL}/subscriptions/admin/usage/export?${params.toString()}`,
		{ headers: { Authorization: `Bearer ${token}` } }
	);
	if (!response.ok) {
		const payload = await response.json().catch(() => null);
		throw payload?.detail ?? `HTTP_${response.status}`;
	}
	return response.blob();
};
