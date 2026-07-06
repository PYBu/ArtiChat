<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getSubscriptionPlans } from '$lib/apis/subscriptions';
	import { refreshSubscription, subscription } from '$lib/stores';

	const dispatch = createEventDispatcher();

	let plans: any[] = [];
	let loading = true;

	const tierLabel = (tier?: string, displayName?: string) => {
		if (tier === 'free') return 'Free';
		if (tier === 'plus') return 'Plus';
		if (tier === 'chatpower') return 'ChatPower';
		return displayName || tier || '-';
	};

	const statusLabel = (status?: string) => {
		if (status === 'active') return '有效';
		if (status === 'expired') return '已过期';
		if (status === 'inactive') return '未启用';
		if (status === 'free') return '有效';
		return status || '-';
	};

	const formatDate = (value?: number | null) => {
		if (!value) return '-';
		return new Date(value * 1000).toLocaleDateString();
	};

	const formatChatpoint = (micros?: number | null) => {
		return ((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2 });
	};

	const load = async () => {
		loading = true;
		const [plansResponse] = await Promise.all([
			getSubscriptionPlans(localStorage.token).catch((error) => {
				toast.error(`${error}`);
				return [];
			}),
			refreshSubscription(localStorage.token)
		]);
		plans = plansResponse ?? [];
		loading = false;
	};

	onMount(load);

	$: currentSubscription = $subscription;
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
	{:else if currentSubscription}
		<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
			<div class="flex items-center justify-between gap-3">
				<div class="font-medium">{tierLabel(currentSubscription.tier, currentSubscription.display_name)}</div>
				<div class="text-xs text-gray-500">{statusLabel(currentSubscription.status)}</div>
			</div>
			<div class="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-300">
				<div>到期时间</div>
				<div class="text-right">{formatDate(currentSubscription.expires_at)}</div>
				<div>本周期开始</div>
				<div class="text-right">{formatDate(currentSubscription.period_start_at)}</div>
				<div>本周期结束</div>
				<div class="text-right">{formatDate(currentSubscription.period_end_at)}</div>
				<div>下次重置</div>
				<div class="text-right">{formatDate(currentSubscription.next_reset_at)}</div>
				<div>Plan Chatpoint</div>
				<div class="text-right">{formatChatpoint(currentSubscription.plan_balance_micros)}</div>
				<div>Check Chatpoint</div>
				<div class="text-right">{formatChatpoint(currentSubscription.check_balance_micros)}</div>
			</div>
		</div>
	{/if}

	<div class="grid gap-3 md:grid-cols-3">
		{#each plans as plan}
			<div class="flex min-h-56 flex-col rounded-lg border border-gray-100 p-4 dark:border-gray-850">
				<div class="flex items-start justify-between gap-3">
					<div>
						<div class="text-base font-medium">{tierLabel(plan.id, plan.display_name)}</div>
						<div class="mt-1 text-xs text-gray-500">{plan.features?.subtitle ?? plan.description}</div>
					</div>
					<div class="rounded-lg bg-gray-100 px-2 py-1 text-xs font-medium uppercase dark:bg-gray-850">
						{plan.features?.icon ?? 'plan'}
					</div>
				</div>

				<div class="mt-4 text-xl font-semibold">{formatChatpoint(plan.plan_chatpoint_allowance_micros)}</div>
				<div class="text-xs text-gray-500">每月 Plan Chatpoint</div>

				<div class="mt-4 flex-1 space-y-2 text-xs text-gray-600 dark:text-gray-300">
					{#each plan.features?.highlights ?? [] as item}
						<div class="flex gap-2">
							<span class="mt-1 size-1.5 rounded-full bg-green-500"></span>
							<span>{item}</span>
						</div>
					{/each}
					<div>{plan.features?.model_summary ?? plan.description}</div>
				</div>

				<button
					type="button"
					class="mt-4 w-full rounded-full bg-gray-100 px-3 py-1.5 text-xs font-medium dark:bg-gray-850"
					on:click={() => toast.info('购买功能暂未开放。')}
				>
					{currentSubscription?.tier === plan.id ? '当前订阅' : (plan.features?.cta_label ?? '购买')}
				</button>
			</div>
		{/each}
	</div>
</div>
