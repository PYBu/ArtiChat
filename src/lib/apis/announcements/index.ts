import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';

export type AnnouncementDisplayMode = 'once' | 'every_login' | 'new_user';

export type Announcement = {
	id: string;
	title: string;
	summary: string;
	body: string;
	image_url: string | null;
	view_button_label: string;
	close_button_label: string;
	display_mode: AnnouncementDisplayMode;
	button_label: string;
	icon: string | null;
	is_active: boolean;
	starts_at: number | null;
	ends_at: number | null;
	sort_order: number;
	created_by: string;
	created_at: number;
	updated_at: number;
};

export type AnnouncementInput = Pick<
	Announcement,
	| 'title'
	| 'summary'
	| 'body'
	| 'image_url'
	| 'view_button_label'
	| 'close_button_label'
	| 'display_mode'
	| 'is_active'
> &
	Partial<Pick<Announcement, 'starts_at' | 'ends_at' | 'sort_order'>>;

export const getActiveAnnouncements = async (token: string) => {
	return apiJsonFetch<{ items: Announcement[] }>(
		`${WEBUI_API_BASE_URL}/announcements/active`,
		token
	);
};

export const markAnnouncementViewed = async (token: string, announcementId: string) => {
	return apiJsonFetch<{ id: string }>(
		`${WEBUI_API_BASE_URL}/announcements/${encodeURIComponent(announcementId)}/viewed`,
		token,
		{ method: 'POST' }
	);
};

export const getAdminAnnouncements = async (token: string, includeInactive = false) => {
	const query = new URLSearchParams({ include_inactive: String(includeInactive) });
	return apiJsonFetch<{ items: Announcement[] }>(
		`${WEBUI_API_BASE_URL}/announcements/admin?${query.toString()}`,
		token
	);
};

export const createAdminAnnouncement = async (token: string, payload: AnnouncementInput) => {
	return apiJsonFetch<Announcement>(`${WEBUI_API_BASE_URL}/announcements/admin`, token, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const updateAdminAnnouncement = async (
	token: string,
	announcementId: string,
	payload: Partial<AnnouncementInput>
) => {
	return apiJsonFetch<Announcement>(
		`${WEBUI_API_BASE_URL}/announcements/admin/${encodeURIComponent(announcementId)}`,
		token,
		{ method: 'PATCH', body: JSON.stringify(payload) }
	);
};

export const deleteAdminAnnouncement = async (token: string, announcementId: string) => {
	return apiJsonFetch<Announcement>(
		`${WEBUI_API_BASE_URL}/announcements/admin/${encodeURIComponent(announcementId)}`,
		token,
		{ method: 'DELETE' }
	);
};
