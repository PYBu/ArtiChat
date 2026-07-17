<script lang="ts">
	import Badge from '$lib/components/icons/UserBadgeCheck.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import ChatBubbles from '$lib/components/icons/ChatBubbles.svelte';
	import DocumentChartBar from '$lib/components/icons/DocumentChartBar.svelte';
	import Grid from '$lib/components/icons/Grid.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';

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
</script>

<div class="mx-auto flex w-full max-w-6xl flex-col px-4 py-4 sm:px-6">
	<div class="border-b border-gray-100 pb-3 dark:border-gray-850">
		<h1 class="text-xl font-medium">订阅运营</h1>
	</div>
	<nav class="grid gap-3 pt-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="订阅运营功能">
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
</div>
