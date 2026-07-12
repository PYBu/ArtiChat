<script lang="ts">
	const sections = [
		{ href: '/admin/subscriptions/plans', title: '订阅计划', description: '管理套餐周期与额度。' },
		{ href: '/admin/subscriptions/models', title: '模型权限', description: '管理模型套餐权限与扣费模式。' },
		{ href: '/admin/subscriptions/redeem-codes', title: '兑换码', description: '创建和停用兑换码。' },
		{ href: '/admin/subscriptions/gift-cards', title: '礼品卡', description: '向用户发放可领取礼品。' },
		{ href: '/admin/subscriptions/announcements', title: '公告', description: '管理登录公告。' },
		{ href: '/admin/subscriptions/users', title: '用户订阅', description: '查看和编辑用户订阅。' },
		{ href: '/admin/subscriptions/usage', title: '用量账本', description: '查看模型用量和余额变更。' }
	];
</script>

<div class="mx-auto flex w-full max-w-5xl flex-col px-4 py-4 sm:px-6">
	<div class="border-b border-gray-100 pb-3 dark:border-gray-850">
		<h1 class="text-xl font-medium">订阅运营</h1>
	</div>
	<nav class="divide-y divide-gray-100 dark:divide-gray-850" aria-label="订阅运营功能">
		{#each sections as section}
			<a href={section.href} class="flex items-center justify-between gap-4 py-4 hover:text-black dark:hover:text-white">
				<div class="min-w-0">
					<div class="font-medium">{section.title}</div>
					<div class="mt-1 text-sm text-gray-500">{section.description}</div>
				</div>
				<span class="flex-none text-gray-400" aria-hidden="true">→</span>
			</a>
		{/each}
	</nav>
</div>
