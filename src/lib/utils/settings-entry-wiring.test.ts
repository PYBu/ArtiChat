import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const read = (path: string) => readFileSync(resolve(path), 'utf8');
const sourceFiles = (directory: string): string[] =>
	readdirSync(resolve(directory), { withFileTypes: true }).flatMap((entry) => {
		const entryPath = `${directory}/${entry.name}`;
		if (entry.isDirectory()) return sourceFiles(entryPath);
		return /\.(svelte|ts)$/.test(entry.name) ? [entryPath] : [];
	});

describe('settings entry wiring', () => {
	it('keeps personal billing entries in the personal modal', () => {
		const modal = read('src/lib/components/chat/SettingsModal.svelte');
		const subscription = read('src/lib/components/chat/Settings/Subscription.svelte');
		const redeem = read('src/lib/components/chat/Settings/RedeemCode.svelte');

		for (const marker of [
			"id: 'subscription'",
			"id: 'redeem_code'",
			"id: 'usage'",
			'<Subscription',
			'<RedeemCode',
			'<UsageCenter'
		]) {
			expect(modal).toContain(marker);
		}
		expect(modal).not.toContain("selectedTab === 'admin:");
		expect(modal).not.toContain('AdminGeneral');
		expect(subscription).toContain('min-h-0 flex-col gap-4 overflow-y-auto');
		expect(redeem).toContain('min-h-0 flex-col overflow-y-auto');
		expect(redeem).toContain('max-w-2xl');
		expect(redeem).toContain('h-7');
		expect(redeem).not.toContain('rounded-full');
	});

	it('mounts quota and gift actions beside the sidebar identity', () => {
		const sidebar = read('src/lib/components/layout/Sidebar.svelte');
		const menu = read('src/lib/components/layout/Sidebar/UserMenu.svelte');

		expect(sidebar).toContain('<PendingGiftEntry');
		expect(sidebar).toContain('<SubscriptionQuotaRing');
		expect(sidebar).toContain("showSettings.set('usage')");
		expect(menu).toContain('export let showQuota = true');
		expect(menu).not.toContain("{#if role !== 'admin'}");
	});

	it('uses a separate admin-only modal with platform and email settings', () => {
		const layout = read('src/routes/(app)/admin/+layout.svelte');
		const adminModal = read('src/lib/components/admin/AdminSettingsModal.svelte');
		const adminSettings = read('src/lib/components/admin/Settings.svelte');
		const operationsHome = read('src/lib/components/admin/Subscriptions/SubscriptionHome.svelte');

		expect(layout).toContain('AdminSettingsModal');
		expect(layout).not.toContain('showSettings');
		expect(adminModal).toContain("$user?.role !== 'admin'");
		expect(adminSettings).toContain("id: 'platform'");
		expect(adminSettings).toContain("id: 'email'");
		expect(adminSettings).toContain("!analyticsEnabled && selectedTab === 'analytics'");
		expect(adminSettings).toContain("selectedTab === 'analytics' && analyticsEnabled");
		expect(layout).toContain("$i18n.t('Operations')");
		expect(layout).not.toContain("$i18n.t('Subscriptions')");
		expect(operationsHome).toContain('运营管理');
		expect(adminSettings.indexOf("id: 'update'")).toBeGreaterThan(
			adminSettings.indexOf("id: 'email'")
		);
		expect(read('src/lib/components/admin/Settings/General.svelte')).not.toContain('WEBUI_VERSION');
	});

	it('routes admin deep links outside the personal settings store', () => {
		const selector = read('src/lib/components/chat/ModelSelector/Selector.svelte');
		const itemMenu = read('src/lib/components/chat/ModelSelector/ModelItemMenu.svelte');
		const terminalMenu = read('src/lib/components/chat/MessageInput/TerminalMenu.svelte');
		const adminSettings = read('src/lib/components/admin/Settings.svelte');

		expect(selector).toContain("goto('/admin/settings/connections')");
		expect(itemMenu).toContain('/admin/settings/models?model=');
		expect(terminalMenu).toContain("goto('/admin/settings/integrations')");
		expect(adminSettings).toContain("$page.url.searchParams.get('model')");

		const offenders = sourceFiles('src').filter((path) => {
			const source = read(path);
			return (
				/showSettings\.set\(\s*['"]admin:/.test(source) ||
				/showSettings\.set\(\s*\{[\s\S]{0,160}?\btab:\s*['"]admin:/.test(source)
			);
		});
		expect(offenders).toEqual([]);
	});

	it('defaults combined usage to authoritative billing without merging activity data', () => {
		const center = read('src/lib/components/chat/Settings/UsageCenter.svelte');
		const billing = read('src/lib/components/chat/Settings/SubscriptionUsage.svelte');
		const activity = read('src/lib/components/chat/Settings/Usage.svelte');

		expect(center).toContain("let view: UsageView = 'billing'");
		expect(center).toContain('<SubscriptionUsage');
		expect(center).toContain('<ActivityUsage');
		for (const field of [
			'total_input_tokens',
			'total_output_tokens',
			'total_cache_creation_tokens',
			'total_cache_read_tokens',
			'total_plan_cost_micros',
			'total_check_cost_micros',
			'total_request_count'
		]) {
			expect(billing).toContain(field);
		}
		expect(activity).not.toContain('getMySubscriptionUsage');
	});

	it('refreshes sidebar subscription state when chat billing completes', () => {
		const chat = read('src/lib/components/chat/Chat.svelte');

		expect(chat).toContain(
			"import { notifySubscriptionChanged } from '$lib/stores/subscriptions';"
		);
		expect(chat.match(/void notifySubscriptionChanged\(\);/g)).toHaveLength(2);
	});

	it('preserves the last subscription snapshot when refresh fails', () => {
		const store = read('src/lib/stores/subscriptions.ts');
		const ring = read('src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte');

		expect(store).toContain('export const subscriptionLoadError = writable(false)');
		expect(store).toContain('subscriptionLoadError.set(true)');
		expect(store).not.toContain('getMySubscription(authToken).catch(() => null)');
		expect(ring).toContain('unavailable = !currentSubscription && $subscriptionLoadError');
		expect(ring).toContain("'stroke-gray-300 dark:stroke-gray-700'");
	});
});
