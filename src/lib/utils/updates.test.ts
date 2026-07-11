import { describe, expect, it } from 'vitest';

import { isActiveUpdateStage, shouldPollUpdate, updateStageLabel } from './updates';

describe('update helpers', () => {
	it('recognizes active deployment stages', () => {
		expect(isActiveUpdateStage('queued')).toBe(true);
		expect(isActiveUpdateStage('verifying')).toBe(true);
		expect(isActiveUpdateStage('completed')).toBe(false);
		expect(isActiveUpdateStage('rolled_back')).toBe(false);
	});

	it('polls while an operation is active', () => {
		expect(shouldPollUpdate({ stage: 'pulling', active: true })).toBe(true);
		expect(shouldPollUpdate({ stage: 'failed', active: false })).toBe(false);
	});

	it('uses a stable Chinese label for every deployment stage', () => {
		expect(updateStageLabel('backing_up')).toBe('正在备份数据');
		expect(updateStageLabel('rolled_back')).toBe('更新失败，已回滚');
	});
});
