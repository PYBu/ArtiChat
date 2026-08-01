import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';

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

export type UpdateAnnouncement = {
	id: string;
	title: string;
	content: string;
	type: 'info' | 'warning' | 'maintenance';
	published_at: string | null;
	expires_at: string | null;
};

export type UpdateAnnouncementResponse = {
	announcement: UpdateAnnouncement | null;
};

export const getUpdateInfo = async (token: string, force = false): Promise<UpdateInfo> =>
	apiJsonFetch(`${WEBUI_API_BASE_URL}/updates/check?force=${force}`, token);

export const getUpdateStatus = async (token: string): Promise<UpdateState> =>
	apiJsonFetch(`${WEBUI_API_BASE_URL}/updates/status`, token);

export const getUpdateAnnouncement = async (token: string): Promise<UpdateAnnouncementResponse> =>
	apiJsonFetch(`${WEBUI_API_BASE_URL}/updates/announcement`, token);

export const deployUpdate = async (token: string, targetVersion: string): Promise<UpdateState> =>
	apiJsonFetch(`${WEBUI_API_BASE_URL}/updates/deploy`, token, {
		method: 'POST',
		body: JSON.stringify({ target_version: targetVersion })
	});
