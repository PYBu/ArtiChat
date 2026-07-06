<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getMySubscription } from '$lib/apis/subscriptions';

	const dispatch = createEventDispatcher();

	let subscription: any = null;
	let loading = true;

	const plans = [
		{ id: 'free', name: '免费版', allowance: '10' },
		{ id: 'plus', name: 'Plus', allowance: '100' },
		{ id: 'chatpower', name: 'ChatPower', allowance: '500' }
	];

	const tierLabel = (tier?: string, displayName?: string) => {
		if (tier === 'free') return '免费版';
		if (tier === 'plus') return 'Plus';
		if (tier === 'chatpower') return 'ChatPower';
		return displayName || tier || '-';
	};

	const statusLabel = (status?: string) => {
		if (status === 'active') return '有效';
		if (status === 'expired') return '已过期';
		if (status === 'inactive') return '未启用';
		return status || '-';
	};

	const formatDate = (value?: number | null) => {
		if (!value) return '-';
		return new Date(value * 1000).toLocaleDateString();
	};

	const formatChatpoint = (micros?: number | null) => {
		return ((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 6 });
	};

	const load = async () => {
		loading = true;
		subscription = await getMySubscription(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		loading = false;
	};

	onMount(load);
</script>

<div id="tab-subscription" class="flex h-full flex-col gap-4 text-sm">
	<div class="flex items-center justify-between gap-3">
		<div class="text-base font-medium">订阅</div>
		<button class="rounded-full px-3 py-1.5 text-xs font-medium hover:bg-gray-100 dark:hover:bg-gray-850" on:click={() => dispatch('redeem')}>
			兑换码
		</button>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if subscription}
		<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
			<div class="flex items-center justify-between gap-3">
				<div class="font-medium">{tierLabel(subscription.tier, subscription.display_name)}</div>
				<div class="text-xs text-gray-500">{statusLabel(subscription.status)}</div>
			</div>
			<div class="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-300">
				<div>到期时间</div>
				<div class="text-right">{formatDate(subscription.expires_at)}</div>
				<div>本周期开始</div>
				<div class="text-right">{formatDate(subscription.period_start_at)}</div>
				<div>本周期结束</div>
				<div class="text-right">{formatDate(subscription.period_end_at)}</div>
				<div>下次重置</div>
				<div class="text-right">{formatDate(subscription.next_reset_at)}</div>
				<div>周期 Chatpoint</div>
				<div class="text-right">{formatChatpoint(subscription.plan_balance_micros)}</div>
				<div>充值 Chatpoint</div>
				<div class="text-right">{formatChatpoint(subscription.check_balance_micros)}</div>
			</div>
		</div>
	{/if}

	<div class="grid gap-2 md:grid-cols-3">
		{#each plans as plan}
			<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
				<div class="font-medium">{plan.name}</div>
				<div class="mt-2 text-xs text-gray-500">{plan.allowance} 周期 Chatpoint</div>
				<button
					type="button"
					class="mt-3 w-full rounded-full bg-gray-100 px-3 py-1.5 text-xs font-medium dark:bg-gray-850"
					on:click={() => toast.info('购买功能暂未开放。')}
				>
					购买
				</button>
			</div>
		{/each}
	</div>
</div>
