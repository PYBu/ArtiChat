<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getMySubscriptionUsage } from '$lib/apis/subscriptions';

	let data: any = null;
	let loading = true;

	const formatChatpoint = (micros?: number | null) => {
		return ((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 6 });
	};

	const formatDate = (value?: number | null) => {
		if (!value) return '-';
		return new Date(value * 1000).toLocaleString();
	};

	onMount(async () => {
		data = await getMySubscriptionUsage(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		loading = false;
	});
</script>

<div id="tab-usage" class="flex h-full flex-col gap-4 text-sm">
	<div class="text-base font-medium">用量</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if data?.subscription}
		<div class="grid gap-2 md:grid-cols-2">
			<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
				<div class="text-xs text-gray-500">周期 Chatpoint</div>
				<div class="mt-1 text-lg font-medium">{formatChatpoint(data.subscription.plan_balance_micros)}</div>
			</div>
			<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
				<div class="text-xs text-gray-500">充值 Chatpoint</div>
				<div class="mt-1 text-lg font-medium">{formatChatpoint(data.subscription.check_balance_micros)}</div>
			</div>
		</div>

		<div>
			<div class="mb-2 font-medium">模型用量</div>
			{#if data.usage?.items?.length}
				<div class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850">
					{#each data.usage.items as item}
						<div class="grid grid-cols-3 gap-2 p-2 text-xs">
							<div>{item.model_id}</div>
							<div>{formatChatpoint(item.cost_micros)}</div>
							<div class="text-right">{formatDate(item.created_at)}</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">暂无用量记录。</div>
			{/if}
		</div>

		<div>
			<div class="mb-2 font-medium">记录</div>
			<div class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850">
				{#each data.ledger ?? [] as entry}
					<div class="grid grid-cols-3 gap-2 p-2 text-xs">
						<div>{entry.event_type}</div>
						<div>{formatChatpoint(entry.plan_delta_micros + entry.check_delta_micros)}</div>
						<div class="text-right">{formatDate(entry.created_at)}</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
