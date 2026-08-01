import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';

export type PlatformSidebarButton = {
	name: string;
	url: string;
	icon: string;
};

export type PlatformSettings = {
	name: string;
	about_title: string;
	about_content: string;
	logo_light: string;
	logo_dark: string;
	sidebar_buttons: PlatformSidebarButton[];
};

export const getPlatformSettings = async (token: string) =>
	apiJsonFetch<PlatformSettings>(`${WEBUI_API_BASE_URL}/configs/platform`, token);

export const setPlatformSettings = async (token: string, settings: PlatformSettings) =>
	apiJsonFetch<PlatformSettings>(`${WEBUI_API_BASE_URL}/configs/platform`, token, {
		method: 'POST',
		body: JSON.stringify(settings)
	});

export const uploadPlatformLogo = async (token: string, theme: 'light' | 'dark', file: File) => {
	const body = new FormData();
	body.append('file', file);

	const response = await fetch(`${WEBUI_API_BASE_URL}/configs/platform/logo/${theme}`, {
		method: 'POST',
		headers: { authorization: `Bearer ${token}` },
		body
	});

	const payload = await response.json().catch(() => null);
	if (!response.ok) throw payload?.detail ?? 'PLATFORM_LOGO_UPLOAD_ERROR';
	return payload as { url: string };
};
