import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { imageEdits } from './index';

describe('image edit api', () => {
	const fetchMock = vi.fn();

	beforeEach(() => {
		fetchMock.mockResolvedValue({ ok: true, json: async () => [] });
		vi.stubGlobal('fetch', fetchMock);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		fetchMock.mockReset();
	});

	it('sends the edit form directly to the FastAPI request body', async () => {
		await imageEdits(
			'token',
			['/api/v1/files/file-1/content'],
			'Change the background',
			'edit-model'
		);

		expect(fetchMock).toHaveBeenCalledOnce();
		expect(fetchMock.mock.calls[0][1]).toMatchObject({
			method: 'POST',
			body: JSON.stringify({
				image: ['/api/v1/files/file-1/content'],
				prompt: 'Change the background',
				model: 'edit-model'
			})
		});
	});
});
