import { WEBUI_API_BASE_URL } from '$lib/constants';

export type AssetSource = 'uploaded' | 'generated';
export type AssetCategory = 'image' | 'video' | 'other';

export type Asset = {
	id: string;
	filename: string;
	source: AssetSource;
	category: AssetCategory;
	content_type?: string | null;
	size?: number | null;
	created_at?: number | null;
	updated_at?: number | null;
	preview_url: string;
	download_url: string;
	active_shares: AssetShare[];
};

export type AssetShare = {
	id: string;
	created_at: number;
	expires_at?: number | null;
};

const authHeaders = (token: string) => ({
	Accept: 'application/json',
	'Content-Type': 'application/json',
	authorization: `Bearer ${token}`
});

const parseError = async (response: Response) => {
	try {
		const payload = await response.json();
		return payload?.detail || payload?.error || `Request failed (${response.status})`;
	} catch {
		return `Request failed (${response.status})`;
	}
};

export const getAssets = async (
	token: string,
	filters: {
		source?: string;
		category?: string;
		query?: string;
		page?: number;
		limit?: number;
	} = {}
) => {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(filters)) {
		if (value) params.set(key, String(value));
	}
	const response = await fetch(`${WEBUI_API_BASE_URL}/assets/?${params.toString()}`, {
		headers: authHeaders(token)
	});
	if (!response.ok) throw new Error(await parseError(response));
	return (await response.json()) as { items: Asset[]; total: number };
};

export const shareAsset = async (
	token: string,
	id: string,
	expiresInDays: number | null = null
) => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/assets/${encodeURIComponent(id)}/share`, {
		method: 'POST',
		headers: authHeaders(token),
		body: JSON.stringify({ expires_in_days: expiresInDays })
	});
	if (!response.ok) throw new Error(await parseError(response));
	return (await response.json()) as {
		id: string;
		file_id: string;
		url: string;
		expires_at?: number | null;
	};
};

export const revokeAssetShare = async (token: string, shareId: string) => {
	const response = await fetch(
		`${WEBUI_API_BASE_URL}/assets/share/${encodeURIComponent(shareId)}`,
		{
			method: 'DELETE',
			headers: authHeaders(token)
		}
	);
	if (!response.ok) throw new Error(await parseError(response));
	return response.json();
};

export const deleteAsset = async (token: string, id: string) => {
	const response = await fetch(`${WEBUI_API_BASE_URL}/files/${encodeURIComponent(id)}`, {
		method: 'DELETE',
		headers: authHeaders(token)
	});
	if (!response.ok) throw new Error(await parseError(response));
	return response.json();
};
