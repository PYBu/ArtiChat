import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const read = (path: string) => readFileSync(resolve(path), 'utf8');

describe('quota and reasoning controls', () => {
	it('keeps quota details in the viewport and routes clicks to usage', () => {
		const ring = read('src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte');

		expect(ring).toContain('import { computePosition, flip, offset, shift }');
		expect(ring).toContain("placement: 'top-end'");
		expect(ring).toContain('shift({ padding: 8 })');
		expect(ring).toContain('if ($mobile)');
		expect(ring).toContain("dispatch('openUsage')");
	});

	it('uses the concise Chinese reasoning label without a default badge', () => {
		const control = read('src/lib/components/chat/MessageInput/ReasoningEffortControl.svelte');
		const zhCN = JSON.parse(read('src/lib/i18n/locales/zh-CN/translation.json'));

		expect(zhCN['Reasoning Effort']).toBe('推理强度');
		expect(control).not.toContain('default-chip');
		expect(control).not.toContain('usesModelDefault');
	});
});
