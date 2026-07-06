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

export const getActiveAnnouncements = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/announcements/active`, token);
};

export const markAnnouncementViewed = async (token: string, announcementId: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/announcements/${encodeURIComponent(announcementId)}/viewed`, token, {
		method: 'POST'
	});
};

export const getAdminAnnouncements = async (token: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/announcements/admin`, token);
};

export const createAdminAnnouncement = async (token: string, payload: Record<string, unknown>) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/announcements/admin`, token, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
};

export const updateAdminAnnouncement = async (
	token: string,
	announcementId: string,
	payload: Record<string, unknown>
) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/announcements/admin/${encodeURIComponent(announcementId)}`, token, {
		method: 'PATCH',
		body: JSON.stringify(payload)
	});
};

export const deleteAdminAnnouncement = async (token: string, announcementId: string) => {
	return jsonFetch(`${WEBUI_API_BASE_URL}/announcements/admin/${encodeURIComponent(announcementId)}`, token, {
		method: 'DELETE'
	});
};
