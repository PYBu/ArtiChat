import type { ReasoningControlConfig, ReasoningLevel, ReasoningProfile } from '$lib/apis';

export const REASONING_LEVELS: ReasoningLevel[] = ['low', 'medium', 'high', 'extra', 'max'];
export const DEFAULT_REASONING_LEVEL: ReasoningLevel = 'high';

export const REASONING_LABELS: Record<ReasoningProfile, Record<ReasoningLevel, string>> = {
	gpt: {
		low: 'Low',
		medium: 'Medium',
		high: 'High',
		extra: 'Extra High',
		max: 'Max'
	},
	claude: {
		low: 'Low',
		medium: 'Medium',
		high: 'High',
		extra: 'Extra',
		max: 'Max'
	}
};

export const isReasoningLevel = (value: unknown): value is ReasoningLevel =>
	typeof value === 'string' && REASONING_LEVELS.includes(value as ReasoningLevel);

export const isReasoningProfile = (value: unknown): value is ReasoningProfile =>
	value === 'gpt' || value === 'claude';

export const suggestReasoningProfile = (
	modelId: string | null | undefined
): ReasoningProfile | null => {
	const normalized = (modelId ?? '').trim().toLowerCase();
	if (!normalized) return null;
	if (normalized.includes('claude')) return 'claude';
	if (/(^|[./:_-])(gpt|codex|o\d)([./:_-]|$)/.test(normalized)) return 'gpt';
	return null;
};

export const getReasoningControl = (model: any): ReasoningControlConfig | null => {
	const value = model?.info?.meta?.reasoning_control ?? model?.meta?.reasoning_control;
	if (!value?.enabled || !isReasoningProfile(value.profile)) return null;
	return { enabled: true, profile: value.profile };
};

export const getReasoningLabel = (profile: ReasoningProfile, level: ReasoningLevel): string =>
	REASONING_LABELS[profile][level];

export const getReasoningLevelIndex = (level: ReasoningLevel): number =>
	Math.max(0, REASONING_LEVELS.indexOf(level));
