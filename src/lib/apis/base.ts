type ApiErrorPayload = {
	detail?: unknown;
};

const errorValue = (payload: unknown, status: number): unknown => {
	if (payload && typeof payload === 'object' && 'detail' in payload) {
		const detail = (payload as ApiErrorPayload).detail;
		if (detail && typeof detail === 'object' && 'code' in detail) {
			const code = (detail as { code: unknown }).code;
			if (code !== null && code !== undefined && code !== '') return code;
		}
		return detail ?? `HTTP_${status}`;
	}
	return payload ?? `HTTP_${status}`;
};

export const apiJsonFetch = async <T>(
	url: string,
	token: string | null,
	options: RequestInit = {}
): Promise<T> => {
	const headers = new Headers(options.headers);
	if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
	if (token) headers.set('Authorization', `Bearer ${token}`);

	const response = await fetch(url, { ...options, headers });
	const payload = await response.json().catch(() => null);
	if (!response.ok) throw errorValue(payload, response.status);
	return payload as T;
};
