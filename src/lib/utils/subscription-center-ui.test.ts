import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const read = (path: string) => readFileSync(resolve(path), 'utf8');

describe('subscription center acceptance copy', () => {
	it('maps both quota guard errors to the next-conversation message', () => {
		const chat = read('src/lib/components/chat/Chat.svelte');

		expect(chat).toContain('CHATPOINT_BALANCE_EXHAUSTED');
		expect(chat).toContain('CHATPOINT_BALANCE_INSUFFICIENT_FOR_INPUT');
		expect(chat).toContain('额度不足支撑下次对话。');
	});

	it('localizes the subscription center header and all three tabs', () => {
		const center = read('src/lib/components/chat/Settings/SubscriptionCenter.svelte');
		const zhCN = JSON.parse(read('src/lib/i18n/locales/zh-CN/translation.json'));

		expect(center).toContain("$i18n.t('Subscription center')");
		expect(center).toContain(
			"$i18n.t('Manage your plan, Chatpoint balance, usage and gift cards.')"
		);
		expect(center).toContain("{ id: 'redeem', label: 'Redeem & Gifts' }");
		expect(center).toContain('let pendingTab: Tab | null = null;');
		expect(center).toContain('!pendingTab');
		expect(center).toContain('min-h-0 min-w-0 flex-1 overflow-hidden pt-5');
		expect(zhCN['Subscription center']).toBe('订阅中心');
		expect(zhCN['Billing usage']).toBe('账单用量');
		expect(zhCN['Redeem & Gifts']).toBe('兑换码与礼品卡');
	});
});
