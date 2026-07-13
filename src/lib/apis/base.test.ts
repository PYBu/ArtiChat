import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiJsonFetch } from './base';

describe('apiJsonFetch', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('forwards cancellation and merges authentication headers', async () => {
		const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
		vi.stubGlobal('fetch', fetchMock);
		const controller = new AbortController();

		await apiJsonFetch('/api/test', 'token', {
			signal: controller.signal,
			headers: { 'X-Request-ID': 'request-1' }
		});

		const options = fetchMock.mock.calls[0][1] as RequestInit;
		const headers = options.headers as Headers;
		expect(options.signal).toBe(controller.signal);
		expect(headers.get('Authorization')).toBe('Bearer token');
		expect(headers.get('X-Request-ID')).toBe('request-1');
	});

	it('throws the stable API detail code', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue({
				ok: false,
				status: 400,
				json: async () => ({ detail: { code: 'SMTP_CONNECTION_FAILED' } })
			})
		);

		await expect(apiJsonFetch('/api/test', null)).rejects.toBe('SMTP_CONNECTION_FAILED');
	});

	it('falls back to the HTTP status when the response has no usable detail', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue({
				ok: false,
				status: 503,
				json: async () => ({ detail: null })
			})
		);

		await expect(apiJsonFetch('/api/test', null)).rejects.toBe('HTTP_503');
	});
});
