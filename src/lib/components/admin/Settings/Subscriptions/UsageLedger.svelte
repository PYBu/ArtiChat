<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getAdminSubscriptionLedger, getAdminSubscriptionUsage } from '$lib/apis/subscriptions';

	let usage: any = { items: [] };
	let ledger: any[] = [];
	let loading = true;

	const formatChatpoint = (micros?: number | null) => ((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 4 });
	const formatDate = (value?: number | null) => (value ? new Date(value * 1000).toLocaleString() : '-');

	const load = async () => {
		loading = true;
		const [usageResponse, ledgerResponse] = await Promise.all([
			getAdminSubscriptionUsage(localStorage.token).catch((error) => {
				toast.error(`${error}`);
				return { items: [] };
			}),
			getAdminSubscriptionLedger(localStorage.token).catch((error) => {
				toast.error(`${error}`);
				return { items: [] };
			})
		]);
		usage = usageResponse ?? { items: [] };
		ledger = ledgerResponse?.items ?? [];
		loading = false;
	};

	onMount(load);
</script>

<div class="flex flex-col gap-4">
	<div class="flex items-center justify-between gap-3">
		<div>
			<div class="text-base font-medium">用量账本</div>
			<div class="text-xs text-gray-500">查看模型用量扣费和订阅余额变动记录。</div>
		</div>
		<button type="button" class="rounded-full px-3 py-1.5 text-xs font-medium hover:bg-gray-100 dark:hover:bg-gray-850" on:click={load}>
			刷新
		</button>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else}
		<div class="grid gap-2 md:grid-cols-3">
			<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
				<div class="text-xs text-gray-500">总扣费 Chatpoint</div>
				<div class="mt-1 text-lg font-medium">{formatChatpoint(usage.total_cost_micros)}</div>
			</div>
			<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
				<div class="text-xs text-gray-500">输入 Token</div>
				<div class="mt-1 text-lg font-medium">{(usage.total_input_tokens ?? 0).toLocaleString()}</div>
			</div>
			<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
				<div class="text-xs text-gray-500">输出 Token</div>
				<div class="mt-1 text-lg font-medium">{(usage.total_output_tokens ?? 0).toLocaleString()}</div>
			</div>
		</div>

		<div>
			<div class="mb-2 font-medium">模型用量</div>
			{#if usage.items?.length}
				<div class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850">
					{#each usage.items as item}
						<div class="grid gap-2 p-2 text-xs md:grid-cols-[1fr_1fr_7rem_7rem_8rem]">
							<div class="truncate">{item.user_id}</div>
							<div class="truncate">{item.model_id}</div>
							<div>{formatChatpoint(item.cost_micros)} CP</div>
							<div>{item.total_tokens?.toLocaleString?.() ?? item.total_tokens} Token</div>
							<div class="text-right">{formatDate(item.created_at)}</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">暂无用量记录。</div>
			{/if}
		</div>

		<div>
			<div class="mb-2 font-medium">余额记录</div>
			{#if ledger.length}
				<div class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850">
					{#each ledger as entry}
						<div class="grid gap-2 p-2 text-xs md:grid-cols-[1fr_8rem_7rem_7rem_8rem]">
							<div class="truncate">{entry.user_id}</div>
							<div>{entry.event_type}</div>
							<div>{formatChatpoint(entry.plan_delta_micros)} 周期</div>
							<div>{formatChatpoint(entry.check_delta_micros)} 充值</div>
							<div class="text-right">{formatDate(entry.created_at)}</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">暂无余额记录。</div>
			{/if}
		</div>
	{/if}
</div>
