<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		getAdminSubscriptionLedger,
		getAdminSubscriptionUsage,
		type SubscriptionLedgerEntry,
		type SubscriptionUsageSummary,
		type UserSummary
	} from '$lib/apis/subscriptions';

	const emptyUsage = (): SubscriptionUsageSummary => ({
		items: [],
		total_cost_micros: 0,
		total_input_tokens: 0,
		total_output_tokens: 0,
		total_cache_creation_tokens: 0,
		total_cache_read_tokens: 0
	});
	let usage = emptyUsage();
	let ledger: SubscriptionLedgerEntry[] = [];
	let loading = true;
	let userFilter = '';
	let modelFilter = '';
	let statusFilter = '';
	let startDate = '';
	let endDate = '';

	const formatChatpoint = (micros?: number | null) =>
		micros === null || micros === undefined
			? '-'
			: (micros / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 6 });
	const formatNumber = (value?: number | null) =>
		value === null || value === undefined ? '-' : value.toLocaleString();
	const formatLatency = (value?: number | null) =>
		value === null || value === undefined ? '-' : `${value.toLocaleString()} ms`;
	const formatDate = (value?: number | null) =>
		value ? new Date(value * 1000).toLocaleString() : '-';
	const userLabel = (item: { user?: UserSummary | null; user_id?: string }) =>
		item.user?.email ?? item.user?.username ?? item.user_id ?? '-';
	const dateToTimestamp = (value: string, endOfDay = false) => {
		if (!value) return undefined;
		const date = new Date(`${value}T${endOfDay ? '23:59:59' : '00:00:00'}`);
		return Math.floor(date.getTime() / 1000);
	};

	const load = async () => {
		loading = true;
		const [usageResponse, ledgerResponse] = await Promise.all([
			getAdminSubscriptionUsage(localStorage.token, {
				userId: userFilter.trim() || undefined,
				modelId: modelFilter.trim() || undefined,
				status: statusFilter || undefined,
				startAt: dateToTimestamp(startDate),
				endAt: dateToTimestamp(endDate, true)
			}).catch((error) => {
				toast.error(`${error}`);
				return emptyUsage();
			}),
			getAdminSubscriptionLedger(localStorage.token).catch((error) => {
				toast.error(`${error}`);
				return { items: [] };
			})
		]);
		usage = usageResponse ?? emptyUsage();
		ledger = ledgerResponse?.items ?? [];
		loading = false;
	};

	const resetFilters = () => {
		userFilter = '';
		modelFilter = '';
		statusFilter = '';
		startDate = '';
		endDate = '';
		load();
	};

	onMount(load);
</script>

<div class="flex flex-col gap-5">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div>
			<div class="text-base font-medium">用量账本</div>
			<div class="text-xs text-gray-500">模型请求审计与订阅余额变动分开记录。</div>
		</div>
		<button
			type="button"
			class="rounded-lg px-3 py-1.5 text-xs font-medium hover:bg-gray-100 dark:hover:bg-gray-850"
			on:click={load}>刷新</button
		>
	</div>

	<div class="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
		<input
			class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-xs dark:border-gray-850"
			bind:value={userFilter}
			placeholder="用户 ID"
		/>
		<input
			class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-xs dark:border-gray-850"
			bind:value={modelFilter}
			placeholder="模型 ID"
		/>
		<select
			class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-xs dark:border-gray-850"
			bind:value={statusFilter}
		>
			<option value="">全部状态</option>
			<option value="billed">已计费</option>
			<option value="unlimited">无限使用</option>
			<option value="admin_bypass">管理员绕过</option>
			<option value="missing_usage">缺少用量</option>
		</select>
		<input
			type="date"
			class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-xs dark:border-gray-850"
			bind:value={startDate}
		/>
		<input
			type="date"
			class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-xs dark:border-gray-850"
			bind:value={endDate}
		/>
		<div class="flex gap-2">
			<button
				type="button"
				class="flex-1 rounded-lg bg-black px-3 py-2 text-xs text-white dark:bg-white dark:text-black"
				on:click={load}>筛选</button
			>
			<button
				type="button"
				class="rounded-lg px-3 py-2 text-xs hover:bg-gray-100 dark:hover:bg-gray-850"
				on:click={resetFilters}>重置</button
			>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else}
		<div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
			{#each [['总扣费 CP', formatChatpoint(usage.total_cost_micros)], ['输入 Token', formatNumber(usage.total_input_tokens ?? 0)], ['输出 Token', formatNumber(usage.total_output_tokens ?? 0)], ['创建缓存', formatNumber(usage.total_cache_creation_tokens ?? 0)], ['读取缓存', formatNumber(usage.total_cache_read_tokens ?? 0)]] as summary}
				<div class="border-b border-gray-100 py-2 dark:border-gray-850">
					<div class="text-xs text-gray-500">{summary[0]}</div>
					<div class="mt-1 text-lg font-medium">{summary[1]}</div>
				</div>
			{/each}
		</div>

		<div>
			<div class="mb-2 font-medium">模型请求</div>
			{#if usage.items?.length}
				<div class="overflow-x-auto border-y border-gray-100 dark:border-gray-850">
					<table class="min-w-[1280px] w-full text-left text-xs">
						<thead class="text-gray-500">
							<tr
								>{#each ['用户', '模型', '输入', '输出', '创建缓存', '读取缓存', '消耗 CP', '首字延迟', '总耗时', '时间', 'IP', '状态'] as heading}<th
										class="px-2 py-2 font-medium">{heading}</th
									>{/each}</tr
							>
						</thead>
						<tbody class="divide-y divide-gray-100 dark:divide-gray-850">
							{#each usage.items as item}
								<tr>
									<td class="max-w-44 truncate px-2 py-2">{userLabel(item)}</td>
									<td class="max-w-48 truncate px-2 py-2">{item.model_id}</td>
									<td class="px-2 py-2">{formatNumber(item.input_tokens)}</td>
									<td class="px-2 py-2">{formatNumber(item.output_tokens)}</td>
									<td class="px-2 py-2">{formatNumber(item.cache_creation_tokens)}</td>
									<td class="px-2 py-2">{formatNumber(item.cache_read_tokens)}</td>
									<td class="px-2 py-2">{formatChatpoint(item.cost_micros)}</td>
									<td class="px-2 py-2">{formatLatency(item.first_token_latency_ms)}</td>
									<td class="px-2 py-2">{formatLatency(item.total_duration_ms)}</td>
									<td class="whitespace-nowrap px-2 py-2">{formatDate(item.created_at)}</td>
									<td class="px-2 py-2">{item.client_ip ?? '-'}</td>
									<td class="px-2 py-2">{item.status}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div class="border-y border-gray-100 py-4 text-gray-500 dark:border-gray-850">
					暂无用量记录。
				</div>
			{/if}
		</div>

		<div>
			<div class="mb-2 font-medium">余额记录</div>
			{#if ledger.length}
				<div
					class="divide-y divide-gray-100 border-y border-gray-100 dark:divide-gray-850 dark:border-gray-850"
				>
					{#each ledger as entry}
						<div class="grid gap-2 py-2 text-xs md:grid-cols-[1fr_8rem_7rem_7rem_10rem]">
							<div class="truncate">{userLabel(entry)}</div>
							<div>{entry.event_type}</div>
							<div>{formatChatpoint(entry.plan_delta_micros)} 周期</div>
							<div>{formatChatpoint(entry.check_delta_micros)} 充值</div>
							<div class="md:text-right">{formatDate(entry.created_at)}</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="border-y border-gray-100 py-4 text-gray-500 dark:border-gray-850">
					暂无余额记录。
				</div>
			{/if}
		</div>
	{/if}
</div>
