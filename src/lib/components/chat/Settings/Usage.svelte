<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getMySubscriptionUsage } from '$lib/apis/subscriptions';
	import { refreshSubscription } from '$lib/stores';

	let data: any = null;
	let loading = true;

	const formatChatpoint = (micros?: number | null) =>
		micros === null || micros === undefined
			? '-'
			: (micros / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 6 });
	const formatNumber = (value?: number | null) =>
		value === null || value === undefined ? '-' : value.toLocaleString();
	const formatLatency = (value?: number | null) =>
		value === null || value === undefined ? '-' : `${value.toLocaleString()} ms`;
	const formatDate = (value?: number | null) => (value ? new Date(value * 1000).toLocaleString() : '-');

	onMount(async () => {
		data = await getMySubscriptionUsage(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		await refreshSubscription(localStorage.token);
		loading = false;
	});
</script>

<div id="tab-usage" class="flex h-full flex-col gap-5 text-sm">
	<div class="text-base font-medium">用量</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if data?.subscription}
		<div class="grid gap-2 md:grid-cols-2">
			<div class="border-b border-gray-100 py-2 dark:border-gray-850"><div class="text-xs text-gray-500">周期 Chatpoint</div><div class="mt-1 text-lg font-medium">{formatChatpoint(data.subscription.plan_balance_micros)}</div></div>
			<div class="border-b border-gray-100 py-2 dark:border-gray-850"><div class="text-xs text-gray-500">充值 Chatpoint</div><div class="mt-1 text-lg font-medium">{formatChatpoint(data.subscription.check_balance_micros)}</div></div>
		</div>

		<div>
			<div class="mb-2 font-medium">模型用量</div>
			{#if data.usage?.items?.length}
				<div class="overflow-x-auto border-y border-gray-100 dark:border-gray-850">
					<table class="min-w-[980px] w-full text-left text-xs">
						<thead class="text-gray-500"><tr>{#each ['模型', '输入', '输出', '创建缓存', '读取缓存', '消耗 CP', '首字延迟', '总耗时', '时间', '状态'] as heading}<th class="px-2 py-2 font-medium">{heading}</th>{/each}</tr></thead>
						<tbody class="divide-y divide-gray-100 dark:divide-gray-850">
							{#each data.usage.items as item}
								<tr>
									<td class="max-w-48 truncate px-2 py-2">{item.model_id}</td>
									<td class="px-2 py-2">{formatNumber(item.input_tokens)}</td>
									<td class="px-2 py-2">{formatNumber(item.output_tokens)}</td>
									<td class="px-2 py-2">{formatNumber(item.cache_creation_tokens)}</td>
									<td class="px-2 py-2">{formatNumber(item.cache_read_tokens)}</td>
									<td class="px-2 py-2">{formatChatpoint(item.cost_micros)}</td>
									<td class="px-2 py-2">{formatLatency(item.first_token_latency_ms)}</td>
									<td class="px-2 py-2">{formatLatency(item.total_duration_ms)}</td>
									<td class="whitespace-nowrap px-2 py-2">{formatDate(item.created_at)}</td>
									<td class="px-2 py-2">{item.status}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div class="border-y border-gray-100 py-4 text-gray-500 dark:border-gray-850">暂无用量记录。</div>
			{/if}
		</div>

		<div>
			<div class="mb-2 font-medium">余额记录</div>
			<div class="divide-y divide-gray-100 border-y border-gray-100 dark:divide-gray-850 dark:border-gray-850">
				{#each data.ledger ?? [] as entry}
					<div class="grid grid-cols-3 gap-2 py-2 text-xs"><div>{entry.event_type}</div><div>{formatChatpoint(entry.plan_delta_micros + entry.check_delta_micros)}</div><div class="text-right">{formatDate(entry.created_at)}</div></div>
				{/each}
			</div>
		</div>
	{/if}
</div>
