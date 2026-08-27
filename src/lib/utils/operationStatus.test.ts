import { describe, expect, it } from 'vitest';

import {
	appendOperationStatus,
	getDefaultOperationStatusConfig,
	getVisibleOperationStatusHistory,
	getToolCallFailureReason,
	getToolCallOperationStatusId,
	resolveOperationStatus
} from './operationStatus';

describe('operation status configuration', () => {
	it('hides video progress by default but keeps failures visible', () => {
		const config = getDefaultOperationStatusConfig();
		const visible = getVisibleOperationStatusHistory(
			[
				{ status_id: 'video.queued', done: false },
				{ status_id: 'video.running', done: false },
				{ status_id: 'video.failed', done: true, error: 'provider unavailable' }
			],
			config
		);

		expect(visible).toHaveLength(1);
		expect(visible[0].status_id).toBe('video.failed');
	});

	it('interpolates custom tool labels', () => {
		const config = getDefaultOperationStatusConfig();
		config.entries['tool.completed'].text = 'Finished {{NAME}}';

		const resolved = resolveOperationStatus(
			{ status_id: 'tool.completed', name: 'search_web' },
			config
		);
		expect(resolved.display_description).toBe('Finished search_web');
		expect(resolved.display_description_custom).toBe(true);
	});

	it('uses image statuses for image-generation tool calls', () => {
		expect(getToolCallOperationStatusId('generate_image', false)).toBe('image.creating');
		expect(getToolCallOperationStatusId('generate_image', true)).toBe('image.succeeded');
		expect(getToolCallOperationStatusId('generate_image', true, true)).toBe('image.failed');
		expect(getToolCallOperationStatusId('edit_image', true)).toBe('image.succeeded');
		expect(getToolCallOperationStatusId('generate_video', true)).toBe('video.succeeded');
		expect(getToolCallOperationStatusId('generate_video', false)).toBe('video.running');
		expect(getToolCallOperationStatusId('generate_video', true, true)).toBe('video.failed');
		expect(getToolCallOperationStatusId('search_web', true)).toBe('tool.completed');
		expect(getToolCallOperationStatusId('search_web', true, true)).toBe('tool.failed');
	});

	it('recognizes common tool failure result shapes', () => {
		expect(getToolCallFailureReason({ error: '[ERROR: Too Many Requests]' })).toBe(
			'[ERROR: Too Many Requests]'
		);
		expect(getToolCallFailureReason({ detail: { error: 'provider unavailable' } })).toBe(
			'provider unavailable'
		);
		expect(getToolCallFailureReason({ status: 'incomplete', message: 'Timed out' })).toBe(
			'Timed out'
		);
		expect(getToolCallFailureReason(undefined, '[ERROR: Too Many Requests]')).toBe(
			'[ERROR: Too Many Requests]'
		);
	});

	it('provides built-in terminal labels for media completion states', () => {
		const config = getDefaultOperationStatusConfig();
		const image = resolveOperationStatus({ status_id: 'image.succeeded' }, config);
		const video = resolveOperationStatus({ status_id: 'video.succeeded' }, config);
		expect(image.display_description).toBe('Image created');
		expect(image.display_description_template).toBe('Image created');
		expect(image.display_description_custom).toBe(false);
		expect(video.display_description).toBe('Video generated');
		expect(video.display_description_template).toBe('Video generated');
		expect(video.display_description_custom).toBe(false);
	});

	it('uses built-in labels when custom text is empty', () => {
		const config = getDefaultOperationStatusConfig();
		config.entries['image.creating'].text = '';
		config.entries['video.succeeded'].text = '';

		expect(
			resolveOperationStatus({ status_id: 'image.creating' }, config).display_description
		).toBe('Creating image');
		expect(
			resolveOperationStatus({ status_id: 'video.succeeded' }, config).display_description
		).toBe('Video generated');
	});

	it('preserves custom media labels exactly', () => {
		const config = getDefaultOperationStatusConfig();
		config.entries['image.creating'].text = '正 在创建图像';

		expect(
			resolveOperationStatus({ status_id: 'image.creating' }, config).display_description
		).toBe('正 在创建图像');
	});

	it('honors global and per-status visibility switches', () => {
		const defaults = getDefaultOperationStatusConfig();
		const hiddenEntry = {
			...defaults,
			entries: {
				...defaults.entries,
				'tool.executing': { visible: false, text: '' }
			}
		};

		expect(
			resolveOperationStatus({ status_id: 'tool.executing', name: 'search_web' }, hiddenEntry)
				.hidden
		).toBe(true);
		expect(
			resolveOperationStatus(
				{ status_id: 'tool.executing', name: 'search_web' },
				{ ...defaults, enabled: false }
			).hidden
		).toBe(true);
	});

	it('merges repeated polling statuses into one history row', () => {
		const config = getDefaultOperationStatusConfig();
		let history = appendOperationStatus([], { status_id: 'video.running', progress: 5 }, config);
		history = appendOperationStatus(history, { status_id: 'video.running', progress: 30 }, config);

		expect(history).toHaveLength(1);
		expect(history[0].progress).toBe(30);
	});

	it('deduplicates repeated rows already stored in message history', () => {
		const config = getDefaultOperationStatusConfig();
		const visible = getVisibleOperationStatusHistory(
			[
				{ status_id: 'web_search.started', done: false },
				{ status_id: 'web_search.started', done: false, query: 'latest news' },
				{ status_id: 'web_search.succeeded', done: true, count: 3 }
			],
			config
		);

		expect(visible).toHaveLength(2);
		expect(visible[0].query).toBe('latest news');
	});
});
