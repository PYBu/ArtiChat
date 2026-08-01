<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Badge from '$lib/components/icons/UserBadgeCheck.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import ChatBubbles from '$lib/components/icons/ChatBubbles.svelte';
	import DocumentChartBar from '$lib/components/icons/DocumentChartBar.svelte';
	import Grid from '$lib/components/icons/Grid.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import {
		getAdminSubscriptionOverview,
		type SubscriptionOverview,
		type SubscriptionOverviewActivity
	} from '$lib/apis/subscriptions';

	const sections = [
		{
			href: '/admin/subscriptions/plans',
			title: '订阅计划',
			description: '管理套餐周期与额度。',
			icon: Badge
		},
		{
			href: '/admin/subscriptions/models',
			title: '模型权限',
			description: '管理模型套餐权限与扣费模式。',
			icon: Grid
		},
		{
			href: '/admin/subscriptions/redeem-codes',
			title: '兑换码',
			description: '创建和停用兑换码。',
			icon: Bolt
		},
		{
			href: '/admin/subscriptions/gift-cards',
			title: '礼品卡',
			description: '向用户发放可领取礼品。',
			icon: Sparkles
		},
		{
			href: '/admin/subscriptions/announcements',
			title: '公告',
			description: '管理登录公告。',
			icon: ChatBubbles
		},
		{
			href: '/admin/subscriptions/usage',
			title: '用量账本',
			description: '查看模型用量和余额变更。',
			icon: DocumentChartBar
		}
	];

	const eventLabels: Record<string, string> = {
		activation: '订阅激活',
		admin_adjustment: '管理员调整',
		admin_update: '管理员调整',
		auto_downgrade: '订阅到期',
		expiry: '订阅到期',
		period_reset: '订阅续期',
		redemption: '兑换订阅',
		renewal: '订阅续期',
		subscription_activation: '订阅激活',
		tier_change: '档位变更'
	};

	let overview: SubscriptionOverview | null = null;
	let loading = true;
	let refreshing = false;
	let error = '';

	const load = async () => {
		if (overview) refreshing = true;
		else loading = true;
		error = '';
		try {
			overview = await getAdminSubscriptionOverview(localStorage.token);
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
			toast.error(error);
		} finally {
			loading = false;
			refreshing = false;
		}
	};

	const formatCount = (value: number) => value.toLocaleString();
	const formatChatpoint = (micros: number) =>
		(micros / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2 });
	const formatChange = (value: number | null) => {
		if (value === null) return '暂无可比数据';
		return `${value > 0 ? '+' : ''}${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}% 本月至今`;
	};
	const formatDate = (value: number) => new Date(value * 1000).toLocaleString();
	const userLabel = (activity: SubscriptionOverviewActivity) =>
		activity.user?.email ?? activity.user?.username ?? activity.user_id;
	const eventLabel = (activity: SubscriptionOverviewActivity) =>
		eventLabels[activity.event_type] ?? '订阅状态变更';
	const eventSource = (activity: SubscriptionOverviewActivity) => {
		if (activity.event_type === 'redemption') return '用户兑换';
		if (activity.event_type === 'period_reset' || activity.event_type === 'renewal') {
			return '系统周期重置';
		}
		if (activity.event_type === 'auto_downgrade' || activity.event_type === 'expiry') {
			return '订阅到期';
		}
		if (
			activity.tier_before &&
			activity.tier_after &&
			activity.tier_before !== activity.tier_after
		) {
			return `${activity.tier_before} → ${activity.tier_after}`;
		}
		return '管理员调整';
	};
	const formatDelta = (planMicros: number, checkMicros: number) => {
		const values: string[] = [];
		if (planMicros) values.push(`Plan ${planMicros > 0 ? '+' : ''}${formatChatpoint(planMicros)}`);
		if (checkMicros) {
			values.push(`Check ${checkMicros > 0 ? '+' : ''}${formatChatpoint(checkMicros)}`);
		}
		return values.length ? values.join(' · ') : '状态更新';
	};

	onMount(load);
</script>

<div
	class="operations-page mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6"
	aria-busy={loading}
>
	<div
		class="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 pb-3 dark:border-gray-850"
	>
		<div>
			<h1 class="text-[14px] font-medium text-gray-900 dark:text-gray-100">运营管理</h1>
			<p class="mt-0.5 text-[11px] text-gray-500">管理订阅权益、兑换与礼品发放、公告和计费账本。</p>
		</div>
		<button
			type="button"
			class="inline-flex h-7 items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 text-[11px] font-medium transition hover:bg-gray-50 disabled:cursor-wait disabled:opacity-60 dark:border-gray-700 dark:hover:bg-gray-850"
			on:click={load}
			disabled={loading || refreshing}
			aria-label="刷新运营概览"
		>
			<span aria-hidden="true">↻</span>
			<span>{refreshing ? '刷新中' : '刷新'}</span>
		</button>
	</div>

	{#if loading}
		<div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
			{#each Array(4) as _}
				<div
					class="h-24 animate-pulse rounded-lg border border-gray-100 bg-gray-50 dark:border-gray-850 dark:bg-gray-900"
				></div>
			{/each}
		</div>
	{:else if error}
		<div
			class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/20 dark:text-red-300"
		>
			<div class="font-medium">运营概览加载失败</div>
			<div class="mt-1 break-words text-xs">{error}</div>
			<button
				type="button"
				class="mt-3 rounded-lg bg-red-700 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-red-800"
				on:click={load}>重试</button
			>
		</div>
	{:else if overview}
		<div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
			<div class="rounded-lg border border-gray-100 p-4 dark:border-gray-850">
				<div class="text-xs text-gray-500">有效订阅</div>
				<div class="mt-2 text-2xl font-medium text-gray-900 dark:text-gray-100">
					{formatCount(overview.metrics.active_subscriptions.count)}
				</div>
				<div class="mt-1 text-xs text-gray-500">
					{formatChange(overview.metrics.active_subscriptions.mtd_change_percent)}
				</div>
			</div>
			<div class="rounded-lg border border-gray-100 p-4 dark:border-gray-850">
				<div class="text-xs text-gray-500">待领取礼品</div>
				<div class="mt-2 text-2xl font-medium text-gray-900 dark:text-gray-100">
					{formatCount(overview.metrics.pending_gifts.count)}
				</div>
				<div class="mt-1 text-xs text-gray-500">
					{formatCount(overview.metrics.pending_gifts.batch_count)} 个批次
				</div>
			</div>
			<div class="rounded-lg border border-gray-100 p-4 dark:border-gray-850">
				<div class="text-xs text-gray-500">今日消耗</div>
				<div class="mt-2 text-2xl font-medium text-gray-900 dark:text-gray-100">
					{formatChatpoint(overview.metrics.daily_deductions.total_micros)}
				</div>
				<div class="mt-1 text-xs text-gray-500">
					Plan {formatChatpoint(overview.metrics.daily_deductions.plan_micros)} · Check {formatChatpoint(
						overview.metrics.daily_deductions.check_micros
					)}
				</div>
			</div>
			<div class="rounded-lg border border-gray-100 p-4 dark:border-gray-850">
				<div class="text-xs text-gray-500">可用兑换码</div>
				<div class="mt-2 text-2xl font-medium text-gray-900 dark:text-gray-100">
					{formatCount(overview.metrics.available_codes.total)}
				</div>
				<div class="mt-1 text-xs text-gray-500">
					订阅 {formatCount(overview.metrics.available_codes.subscription)} · 充值 {formatCount(
						overview.metrics.available_codes.recharge
					)}{#if overview.metrics.available_codes.legacy}
						· 旧版 {formatCount(overview.metrics.available_codes.legacy)}{/if}
				</div>
			</div>
		</div>

		<section>
			<div class="mb-2 flex items-center justify-between gap-3">
				<h2 class="text-sm font-medium text-gray-900 dark:text-gray-100">运营工具</h2>
				<span class="text-xs text-gray-500">{sections.length} 个模块</span>
			</div>
			<nav class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="运营管理功能">
				{#each sections as section}
					<a
						href={section.href}
						class="group flex min-h-32 flex-col justify-between rounded-lg border border-gray-100 p-4 transition hover:border-gray-200 hover:bg-gray-50/70 dark:border-gray-850 dark:hover:border-gray-700 dark:hover:bg-gray-900"
					>
						<div class="flex items-start justify-between gap-4">
							<div
								class="flex size-9 items-center justify-center rounded-lg bg-gray-100 text-gray-700 dark:bg-gray-850 dark:text-gray-200"
							>
								<svelte:component this={section.icon} className="size-4.5" />
							</div>
							<span class="text-gray-400 transition group-hover:translate-x-0.5" aria-hidden="true"
								>→</span
							>
						</div>
						<div class="min-w-0 pt-4">
							<div class="font-medium text-gray-900 dark:text-gray-100">{section.title}</div>
							<div class="mt-1 text-sm text-gray-500">{section.description}</div>
						</div>
					</a>
				{/each}
			</nav>
		</section>

		<section>
			<div class="mb-2 flex flex-wrap items-center justify-between gap-2">
				<h2 class="text-sm font-medium text-gray-900 dark:text-gray-100">最近订阅变动</h2>
				<a
					href="/admin/subscriptions/usage"
					class="text-xs text-gray-500 transition hover:text-gray-900 dark:hover:text-gray-100"
					>查看订阅账本 →</a
				>
			</div>
			{#if overview.recent_activity.length}
				<div class="overflow-x-auto rounded-lg border border-gray-100 dark:border-gray-850">
					<table class="w-full min-w-[680px] text-left text-xs">
						<thead class="bg-gray-50 text-gray-500 dark:bg-gray-900">
							<tr>
								<th class="px-3 py-2 font-medium">用户</th>
								<th class="px-3 py-2 font-medium">事件</th>
								<th class="px-3 py-2 font-medium">来源</th>
								<th class="px-3 py-2 font-medium">Chatpoint</th>
								<th class="px-3 py-2 font-medium">时间</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-100 dark:divide-gray-850">
							{#each overview.recent_activity as activity}
								<tr>
									<td class="max-w-52 truncate px-3 py-2.5 text-gray-900 dark:text-gray-100"
										>{userLabel(activity)}</td
									>
									<td class="px-3 py-2.5">{eventLabel(activity)}</td>
									<td class="px-3 py-2.5 text-gray-500">{eventSource(activity)}</td>
									<td class="whitespace-nowrap px-3 py-2.5"
										>{formatDelta(activity.plan_delta_micros, activity.check_delta_micros)}</td
									>
									<td class="whitespace-nowrap px-3 py-2.5 text-gray-500"
										>{formatDate(activity.created_at)}</td
									>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div
					class="rounded-lg border border-dashed border-gray-200 p-6 text-center text-sm text-gray-500 dark:border-gray-800"
				>
					暂无订阅变动记录
				</div>
			{/if}
		</section>
	{/if}
</div>

<style>
	.operations-page :global(.text-2xl) {
		font-size: 1.25rem;
		line-height: 1.5rem;
	}

	.operations-page :global(.text-xl),
	.operations-page :global(.text-lg),
	.operations-page :global(.text-base) {
		font-size: 0.875rem;
		line-height: 1.25rem;
	}

	.operations-page :global(.text-sm) {
		font-size: 0.75rem;
		line-height: 1rem;
	}
</style>
