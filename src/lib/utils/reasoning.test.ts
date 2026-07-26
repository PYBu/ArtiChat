import { describe, expect, it } from 'vitest';

import {
	DEFAULT_REASONING_LEVEL,
	getReasoningControl,
	getReasoningLabel,
	isReasoningLevel,
	suggestReasoningProfile
} from './reasoning';

describe('reasoning control helpers', () => {
	it('suggests profiles from model IDs without inspecting provider URLs', () => {
		expect(suggestReasoningProfile('gpt-5.6')).toBe('gpt');
		expect(suggestReasoningProfile('openai/codex-mini')).toBe('gpt');
		expect(suggestReasoningProfile('claude-opus-4-1')).toBe('claude');
		expect(suggestReasoningProfile('custom-reasoner')).toBeNull();
	});

	it('returns only enabled, valid saved controls', () => {
		expect(
			getReasoningControl({
				info: { meta: { reasoning_control: { enabled: true, profile: 'gpt' } } }
			})
		).toEqual({ enabled: true, profile: 'gpt' });
		expect(
			getReasoningControl({
				info: { meta: { reasoning_control: { enabled: false, profile: 'gpt' } } }
			})
		).toBeNull();
		expect(
			getReasoningControl({
				info: { meta: { reasoning_control: { enabled: true, profile: 'other' } } }
			})
		).toBeNull();
	});

	it('uses five stable levels and family-specific fourth labels', () => {
		expect(DEFAULT_REASONING_LEVEL).toBe('high');
		expect(isReasoningLevel('max')).toBe(true);
		expect(isReasoningLevel('ultra')).toBe(false);
		expect(getReasoningLabel('gpt', 'extra')).toBe('Extra High');
		expect(getReasoningLabel('claude', 'extra')).toBe('Extra');
	});
});
