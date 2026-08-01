import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	loadDirectConnections,
	mergeLocalDirectConnections,
	prepareUserSettingsForServer
} from './direct-connections';

describe('direct connection secret storage', () => {
	const token = `header.${btoa(JSON.stringify({ id: 'user-1' }))}.signature`;
	const storedValues = new Map<string, string>();
	const storage = {
		getItem: (key: string) => storedValues.get(key) ?? null,
		setItem: (key: string, value: string) => storedValues.set(key, value),
		removeItem: (key: string) => storedValues.delete(key),
		clear: () => storedValues.clear()
	};

	beforeEach(() => {
		storage.clear();
		vi.stubGlobal('localStorage', storage);
	});

	it('keeps direct connection keys in browser storage and strips the server payload', () => {
		const payload = prepareUserSettingsForServer(token, {
			ui: {
				theme: 'dark',
				directConnections: {
					OPENAI_API_BASE_URLS: ['https://api.example/v1'],
					OPENAI_API_KEYS: ['provider-secret'],
					OPENAI_API_CONFIGS: {}
				}
			}
		});

		expect(payload).toEqual({ ui: { theme: 'dark' } });
		expect(loadDirectConnections(token)?.OPENAI_API_KEYS).toEqual(['provider-secret']);
	});

	it('merges local connections into settings returned by the server', () => {
		prepareUserSettingsForServer(token, {
			ui: {
				directConnections: {
					OPENAI_API_BASE_URLS: ['https://api.example/v1'],
					OPENAI_API_KEYS: ['provider-secret'],
					OPENAI_API_CONFIGS: {}
				}
			}
		});

		const merged = mergeLocalDirectConnections(token, { ui: { theme: 'light' } });
		expect(merged.ui.theme).toBe('light');
		expect(merged.ui.directConnections.OPENAI_API_KEYS).toEqual(['provider-secret']);
	});

	it('isolates connections between users on the same browser', () => {
		const anotherToken = `header.${btoa(JSON.stringify({ id: 'user-2' }))}.signature`;
		prepareUserSettingsForServer(token, {
			ui: {
				directConnections: {
					OPENAI_API_BASE_URLS: ['https://api.example/v1'],
					OPENAI_API_KEYS: ['provider-secret'],
					OPENAI_API_CONFIGS: {}
				}
			}
		});

		expect(loadDirectConnections(anotherToken)).toBeNull();
	});
});
