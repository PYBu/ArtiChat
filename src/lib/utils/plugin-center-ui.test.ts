import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const read = (path: string) => readFileSync(resolve(path), 'utf8');

describe('plugin center visual shell', () => {
	it('adds a compact plugin center entry to operations', () => {
		const home = read('src/lib/components/admin/Subscriptions/SubscriptionHome.svelte');

		expect(home).toContain("href: '/admin/subscriptions/plugins'");
		expect(home).toContain("title: '插件中心'");
		expect(home).toContain('min-h-[6.5rem]');
		expect(home).toContain('grid gap-2 sm:grid-cols-2 lg:grid-cols-3');
	});

	it('keeps the plugin center local-only until the plugin contract is approved', () => {
		const page = read('src/lib/components/admin/Subscriptions/PluginCenter.svelte');
		const route = read('src/routes/(app)/admin/subscriptions/plugins/+page.svelte');
		const normalizedPage = page.replace(/\s+/g, ' ');

		expect(route).toContain('PluginCenter');
		expect(page).toContain('ACPlugin');
		expect(page).toContain('未连接');
		expect(page).toContain('ACP 目录');
		expect(page).toContain('个人上传');
		expect(page).toContain('let autoSync = false;');
		expect(page).toContain('邮箱助手');
		expect(page).toContain("status: 'development'");
		expect(normalizedPage).toContain('disabled > 开发中 </button>');
		expect(page).toContain('cursor-not-allowed');
		expect(page).not.toContain("status: 'preview'");
		expect(page).not.toContain('installPlugin');
		expect(page).not.toContain('togglePlugin');
		expect(page).not.toContain('enabledPlugins');
		expect(normalizedPage).toContain(
			'ArtiChat 插件功能属于内测项，可能存在优化问题。ACPlugin 提供的项目均已验证，自行加载插件需谨慎。'
		);
		expect(page).toContain('插件安全边界');
		expect(page).not.toContain('网页引用');
		expect(page).not.toContain('工作区导出');
		expect(page).not.toContain('代码审阅器');
		expect(page).not.toContain('社区上传');
		expect(page).not.toContain('默认关闭');
		expect(page).not.toContain('视觉示例');
		expect(page).not.toContain('$lib/apis/plugins');
	});

	it('keeps the route behind the existing admin shell', () => {
		const adminLayout = read('src/routes/(app)/admin/+layout.svelte');

		expect(adminLayout).toContain("if ($user?.role !== 'admin')");
		expect(adminLayout).toContain('{#if loaded}');
		expect(adminLayout).toContain('<slot />');
	});
});
