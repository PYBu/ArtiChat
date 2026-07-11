import { WEBUI_API_BASE_URL } from '$lib/constants';

export type UpdateStage =
	| 'idle'
	| 'queued'
	| 'preparing'
	| 'pulling'
	| 'backing_up'
	| 'restarting'
	| 'verifying'
	| 'completed'
	| 'failed'
	| 'rolled_back';

export type UpdateState = {
	operation_id?: string;
	target_version?: string;
	previous_version?: string | null;
	stage: UpdateStage;
	active: boolean;
	message?: string | null;
	error?: string | null;
	updated_at: number;
};

export type ReleaseInfo = {
	version: string;
	name: string;
	body: string;
	published_at: string;
	html_url: string;
};

export type UpdateInfo = {
	current: string;
	latest: string;
	display_version: string;
	build_hash: string;
	update_available: boolean;
	deployment_enabled: boolean;
	release: ReleaseInfo | null;
	status: UpdateState;
	error: string | null;
};

const jsonFetch = async <T>(url: string, token: string, options: RequestInit = {}): Promise<T> => {
	let error = null;
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
		.catch((caught) => {
			error = caught;
			return null;
		});

	if (error) throw error;
	return response as T;
};

export const getUpdateInfo = async (token: string, force = false): Promise<UpdateInfo> =>
	jsonFetch(`${WEBUI_API_BASE_URL}/updates/check?force=${force}`, token);

export const getUpdateStatus = async (token: string): Promise<UpdateState> =>
	jsonFetch(`${WEBUI_API_BASE_URL}/updates/status`, token);

export const deployUpdate = async (token: string, targetVersion: string): Promise<UpdateState> =>
	jsonFetch(`${WEBUI_API_BASE_URL}/updates/deploy`, token, {
		method: 'POST',
		body: JSON.stringify({ target_version: targetVersion })
	});
