import { VIDEO_API_BASE_URL } from '$lib/constants';

const request = async (token: string, path: string, options: RequestInit = {}) => {
	const response = await fetch(`${VIDEO_API_BASE_URL}${path}`, {
		...options,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` }),
			...(options.headers ?? {})
		}
	});

	if (!response.ok) {
		const body = await response.json().catch(() => ({}));
		const detail = Array.isArray(body?.detail)
			? body.detail.map((item: { msg?: string }) => item?.msg ?? JSON.stringify(item)).join(', ')
			: body?.detail;
		throw new Error(detail || 'Server connection failed');
	}

	return response.json();
};

export const getVideoGenerationConfig = (token: string = '') => request(token, '/config');

export const updateVideoGenerationConfig = (token: string = '', config: object) =>
	request(token, '/config/update', {
		method: 'POST',
		body: JSON.stringify(config)
	});

export const getVideoGenerationEstimate = (token: string = '', duration?: number) =>
	request(token, `/estimate${duration === undefined ? '' : `?duration=${encodeURIComponent(duration)}`}`);

export const videoGenerations = (
	token: string = '',
	data: {
		prompt: string;
		model?: string;
		first_frame_url?: string;
		duration?: number;
		resolution?: string;
		ratio?: string;
		watermark?: boolean;
		confirm_cost?: boolean;
		chat_id?: string;
		message_id?: string;
	}
) =>
	request(token, '/generations', {
		method: 'POST',
		body: JSON.stringify(data)
	});

export const getVideoGenerationJobs = (token: string = '', limit = 50) =>
	request(token, `/jobs?limit=${Math.max(1, Math.min(100, limit))}`);

export const getVideoGenerationJob = (token: string = '', jobId: string) =>
	request(token, `/jobs/${encodeURIComponent(jobId)}`);

export const cancelVideoGenerationJob = (token: string = '', jobId: string) =>
	request(token, `/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' });
