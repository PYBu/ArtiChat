import { describe, expect, it } from 'vitest';
import { resolveMediaGenerations } from './mediaGenerations';

describe('resolveMediaGenerations', () => {
	it('uses an image file to complete a single pending image generation', () => {
		const pending = { tool_call_id: 'image-call', media_type: 'image', phase: 'start' } as const;
		const file = { id: 'image-1', type: 'image', url: '/files/image-1' };

		expect(resolveMediaGenerations([pending], [file])).toEqual([
			{ ...pending, phase: 'success', files: [file] }
		]);
	});

	it('does not reassign files already claimed by another generation', () => {
		const existing = {
			tool_call_id: 'old-call',
			media_type: 'image',
			phase: 'success',
			files: [{ id: 'old-image', type: 'image' }]
		} as const;
		const pending = { tool_call_id: 'new-call', media_type: 'image', phase: 'start' } as const;
		const newFile = { id: 'new-image', type: 'image', url: '/files/new-image' };

		expect(resolveMediaGenerations([existing, pending], [existing.files[0], newFile])).toEqual([
			existing,
			{ ...pending, phase: 'success', files: [newFile] }
		]);
	});

	it('only associates files with the pending generation media type', () => {
		const pending = { tool_call_id: 'video-call', media_type: 'video', phase: 'start' } as const;
		const image = { id: 'image-1', type: 'image' };
		const video = { id: 'video-1', type: 'video' };

		expect(resolveMediaGenerations([pending], [image, video])).toEqual([
			{ ...pending, phase: 'success', files: [video] }
		]);
	});

	it('leaves ambiguous parallel pending generations unchanged', () => {
		const pending = [
			{ tool_call_id: 'first-call', media_type: 'image', phase: 'start' },
			{ tool_call_id: 'second-call', media_type: 'image', phase: 'start' }
		] as const;

		expect(resolveMediaGenerations([...pending], [{ id: 'image-1', type: 'image' }])).toEqual(
			pending
		);
	});
});
