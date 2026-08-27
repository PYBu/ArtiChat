import { WEBUI_API_BASE_URL } from '$lib/constants';

/** Resolve file IDs while preserving URLs already returned by the API. */
export const resolveFileContentUrl = (url: string | null | undefined): string => {
	const value = url?.trim() ?? '';
	if (!value) return '';
	if (/^(?:data:|blob:|https?:)/i.test(value) || value.startsWith('/')) return value;
	return `${WEBUI_API_BASE_URL}/files/${encodeURIComponent(value)}/content`;
};
