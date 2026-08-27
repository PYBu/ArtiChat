import { describe, expect, it } from 'vitest';

import {
	appendOperationStatus,
	getDefaultOperationStatusConfig,
	getVisibleOperationStatusHistory,
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

		expect(
			resolveOperationStatus({ status_id: 'tool.completed', name: 'search_web' }, config)
				.display_description
		).toBe('Finished search_web');
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
