import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';

export type MarketplaceModel = {
	id: string;
	name: string;
	description: string;
	long_description: string;
	is_active: boolean;
	allowed_tiers: string[];
	quota_mode: 'metered' | 'unlimited';
	pricing: {
		input: string;
		output: string;
		cache_creation: string;
		cache_read: string;
	};
	restricted_access: boolean;
	history: Array<{ date: string; count: number }>;
};

export const getModelMarketplace = async (token: string) =>
	apiJsonFetch<MarketplaceModel[]>(`${WEBUI_API_BASE_URL}/models/marketplace`, token);
