import { describe, expect, it } from 'vitest';

import { resolveFileContentUrl } from './fileUrls';

describe('resolveFileContentUrl', () => {
	it('turns a file id into the authenticated content endpoint', () => {
		expect(resolveFileContentUrl('file-123')).toBe('/api/v1/files/file-123/content');
	});

	it('preserves API paths already returned by the backend', () => {
		expect(resolveFileContentUrl('/api/v1/files/file-123/content')).toBe(
			'/api/v1/files/file-123/content'
		);
	});

	it('preserves remote, blob, and data URLs', () => {
		expect(resolveFileContentUrl('https://cdn.example/video.mp4')).toBe(
			'https://cdn.example/video.mp4'
		);
		expect(resolveFileContentUrl('blob:https://chat.example/video')).toBe(
			'blob:https://chat.example/video'
		);
		expect(resolveFileContentUrl('data:video/mp4;base64,AAAA')).toBe('data:video/mp4;base64,AAAA');
	});

	it('returns an empty URL for missing values', () => {
		expect(resolveFileContentUrl(null)).toBe('');
	});
});
