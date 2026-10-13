import { describe, expect, it } from 'vitest';
import {
	ARTIAPI_BASE_URL,
	getArtiAPIKeys,
	mergeArtiAPIKeys,
	type OpenAIProviderConfig
} from './artiAPIConnections';

const fixture = (): OpenAIProviderConfig => ({
	ENABLE_OPENAI_API: true,
	OPENAI_API_BASE_URLS: [
		'https://first.example/v1',
		ARTIAPI_BASE_URL,
		'https://last.example/v1',
		`${ARTIAPI_BASE_URL}/`
	],
	OPENAI_API_KEYS: ['test-first', 'test-arti-one', 'test-last', 'test-arti-two'],
	OPENAI_API_CONFIGS: {
		'0': { enable: true, prefix_id: 'first' },
		'1': { enable: true, model_ids: ['model-one'], prefix_id: 'arti-one' },
		'2': { enable: false, model_ids: ['last-model'], extra: 'preserve' },
		'3': { enable: false, model_ids: ['model-two'], prefix_id: 'arti-two' }
	}
});

describe('ArtiAPI key configuration', () => {
	it('restores every ArtiAPI key, including a URL with a trailing slash', () => {
		expect(getArtiAPIKeys(fixture()).map((entry) => [entry.key, entry.config.model_ids])).toEqual([
			['test-arti-one', ['model-one']],
			['test-arti-two', ['model-two']]
		]);
	});

	it('deletes one key while keeping the remaining key and unrelated indexed settings paired', () => {
		const current = fixture();
		const remaining = getArtiAPIKeys(current)[1];
		const merged = mergeArtiAPIKeys(current, [
			{
				...remaining,
				originalKey: remaining.key,
				config: { enable: true, model_ids: ['chosen-two'] }
			}
		]);
		expect(merged.OPENAI_API_BASE_URLS).toEqual([
			'https://first.example/v1',
			ARTIAPI_BASE_URL,
			'https://last.example/v1'
		]);
		expect(merged.OPENAI_API_KEYS).toEqual(['test-first', 'test-arti-two', 'test-last']);
		expect(merged.OPENAI_API_CONFIGS).toEqual({
			'0': current.OPENAI_API_CONFIGS['0'],
			'1': { enable: true, model_ids: ['chosen-two'], prefix_id: 'arti-two' },
			'2': current.OPENAI_API_CONFIGS['2']
		});
		expect(current).toEqual(fixture());
	});

	it('adds separate keys with independent enabled states and model selections', () => {
		const current = fixture();
		const merged = mergeArtiAPIKeys(current, [
			...getArtiAPIKeys(current),
			{ key: ' test-arti-three ', config: { enable: true, model_ids: ['model-three'] } }
		]);
		expect(
			getArtiAPIKeys(merged).map((entry) => [
				entry.key,
				entry.config.enable,
				entry.config.model_ids
			])
		).toEqual([
			['test-arti-one', true, ['model-one']],
			['test-arti-two', false, ['model-two']],
			['test-arti-three', true, ['model-three']]
		]);
	});

	it('removes all ArtiAPI keys without disabling or deleting other providers', () => {
		const merged = mergeArtiAPIKeys(fixture(), []);
		expect(merged.ENABLE_OPENAI_API).toBe(true);
		expect(merged.OPENAI_API_KEYS).toEqual(['test-first', 'test-last']);
		expect(merged.OPENAI_API_CONFIGS['1']).toEqual(fixture().OPENAI_API_CONFIGS['2']);
	});

	it('preserves legacy URL-based metadata and the latest settings when a key is edited', () => {
		const current: OpenAIProviderConfig = {
			ENABLE_OPENAI_API: false,
			OPENAI_API_BASE_URLS: [ARTIAPI_BASE_URL, 'https://other.example/v1'],
			OPENAI_API_KEYS: ['test-old', 'test-other'],
			OPENAI_API_CONFIGS: {
				[ARTIAPI_BASE_URL]: { prefix_id: 'kept' },
				'https://other.example/v1': { enable: true, extra: 'latest' }
			}
		};
		const merged = mergeArtiAPIKeys(current, [
			{ key: 'test-new', originalKey: 'test-old', config: { enable: true, model_ids: ['allowed'] } }
		]);
		expect(merged.ENABLE_OPENAI_API).toBe(true);
		expect(merged.OPENAI_API_CONFIGS['0']).toEqual({
			prefix_id: 'kept',
			enable: true,
			model_ids: ['allowed']
		});
		expect(merged.OPENAI_API_CONFIGS['1']).toEqual({ enable: true, extra: 'latest' });
	});
});
