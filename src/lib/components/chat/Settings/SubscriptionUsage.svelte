<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import { getMySubscriptionUsage, type SubscriptionUsageResponse } from '$lib/apis/subscriptions';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n: Writable<any> = getContext('i18n');
	let loading = true;
	let data: SubscriptionUsageResponse | null = null;

	const formatChatpoint = (micros: number | null | undefined) =>
		((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 6 });
	const formatDate = (value: number | null | undefined) =>
		value ? new Date(value * 1000).toLocaleString() : '-';
	const formatDuration = (value: number | null | undefined) =>
		value == null ? '-' : value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value} ms`;
	const deductedCost = (plan: number, check: number) => plan + check;

	onMount(async () => {
		data = await getMySubscriptionUsage(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		loading = false;
	});
</script>

<div class="flex h-full min-h-0 flex-col text-sm">
	{#if loading}
		<div class="flex flex-1 items-center justify-center py-12"><Spinner className="size-5" /></div>
	{:else if !data}
		<div class="border-y border-gray-100 py-12 text-center text-gray-500 dark:border-gray-850">
			{$i18n.t('Billing usage is currently unavailable.')}
		</div>
	{:else}
		<div
			class="scrollbar-hover min-h-0 flex-1 overflow-y-auto pr-1.5"
			style="scrollbar-gutter: stable;"
		>
			<div
				class="flex flex-wrap items-end justify-between gap-2 border-b border-gray-100 pb-3 dark:border-gray-850"
			>
				<div>
					<h3 class="text-[13px] font-medium text-gray-700 dark:text-gray-200">
						{$i18n.t('Current billing period')}
					</h3>
					<div class="mt-1 text-[0.6875rem] text-gray-500 dark:text-gray-400">
						{formatDate(data.subscription.period_start_at)} - {formatDate(
							data.subscription.period_end_at
						)}
					</div>
				</div>
				<div class="text-right">
					<div class="text-sm font-medium text-gray-900 dark:text-white">
						{formatChatpoint(
							deductedCost(data.usage.total_plan_cost_micros, data.usage.total_check_cost_micros)
						)} CP
					</div>
					<div class="mt-0.5 text-[0.6875rem] text-gray-500">
						{$i18n.t('Chatpoint deducted')}
					</div>
				</div>
			</div>

			<section
				class="grid grid-cols-2 gap-x-6 gap-y-4 border-b border-gray-100 py-4 md:grid-cols-4 dark:border-gray-850"
			>
				<div>
					<div class="text-[13px] font-medium">
						{formatChatpoint(data.subscription.plan_balance_micros)}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">Plan Chatpoint</div>
				</div>
				<div>
					<div class="text-[13px] font-medium">
						{formatChatpoint(data.subscription.check_balance_micros)}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">Check Chatpoint</div>
				</div>
				<div>
					<div class="text-[13px] font-medium">
						{formatChatpoint(data.usage.total_plan_cost_micros)}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">{$i18n.t('Plan deducted')}</div>
				</div>
				<div>
					<div class="text-[13px] font-medium">
						{formatChatpoint(data.usage.total_check_cost_micros)}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">{$i18n.t('Check deducted')}</div>
				</div>
			</section>

			<section
				class="grid grid-cols-2 gap-x-6 gap-y-4 border-b border-gray-100 py-4 md:grid-cols-3 xl:grid-cols-5 dark:border-gray-850"
			>
				<div>
					<div class="text-[13px] font-medium">
						{data.usage.total_input_tokens.toLocaleString()}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">{$i18n.t('Input tokens')}</div>
				</div>
				<div>
					<div class="text-[13px] font-medium">
						{data.usage.total_output_tokens.toLocaleString()}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">{$i18n.t('Output tokens')}</div>
				</div>
				<div>
					<div class="text-[13px] font-medium">
						{data.usage.total_cache_creation_tokens.toLocaleString()}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">{$i18n.t('Cache creation tokens')}</div>
				</div>
				<div>
					<div class="text-[13px] font-medium">
						{data.usage.total_cache_read_tokens.toLocaleString()}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">{$i18n.t('Cache read tokens')}</div>
				</div>
				<div>
					<div class="text-[13px] font-medium">
						{data.usage.total_request_count.toLocaleString()}
					</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500">{$i18n.t('Requests')}</div>
				</div>
			</section>

			{#if data.usage.total_unpaid_cost_micros > 0}
				<div
					class="border-b border-gray-100 py-3 text-[0.6875rem] text-amber-700 dark:border-gray-850 dark:text-amber-300"
				>
					{$i18n.t('Unpaid cost recorded for audit')}: {formatChatpoint(
						data.usage.total_unpaid_cost_micros
					)} CP
				</div>
			{/if}

			<section class="py-4">
				<h3 class="mb-3 text-[0.6875rem] font-medium text-gray-500">
					{$i18n.t('Billing usage by model')}
				</h3>
				{#if data.usage.model_totals.length}
					<div class="divide-y divide-gray-100 dark:divide-gray-850">
						{#each data.usage.model_totals as model}
							<div
								class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 py-2.5 sm:grid-cols-[minmax(0,1fr)_auto_auto]"
							>
								<div class="min-w-0 truncate font-medium">{model.model_id}</div>
								<div class="hidden text-[0.6875rem] text-gray-500 sm:block">
									{model.request_count.toLocaleString()}
									{$i18n.t('requests')} - {model.total_tokens.toLocaleString()}
									{$i18n.t('tokens')}
								</div>
								<div class="min-w-20 text-right text-[0.6875rem]">
									{formatChatpoint(deductedCost(model.plan_cost_micros, model.check_cost_micros))} CP
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="text-[0.6875rem] text-gray-500">
						{$i18n.t('No model usage in this period.')}
					</div>
				{/if}
			</section>

			<section class="border-t border-gray-100 pt-4 dark:border-gray-850">
				<h3 class="mb-2 text-[0.6875rem] font-medium text-gray-500">
					{$i18n.t('Recent billed requests')}
				</h3>
				{#if data.usage.items.length}
					<div class="divide-y divide-gray-100 dark:divide-gray-850">
						{#each data.usage.items as item}
							<div class="py-3">
								<div class="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-1">
									<div class="min-w-0 truncate font-medium">{item.model_id}</div>
									<div class="flex shrink-0 items-center gap-2 text-[0.6875rem] text-gray-500">
										<span>{item.status}</span>
										<span>{formatDate(item.created_at)}</span>
									</div>
								</div>
								<div
									class="mt-2 grid grid-cols-2 gap-x-5 gap-y-2 text-[0.6875rem] sm:grid-cols-3 lg:grid-cols-6"
								>
									<div>
										<span class="text-gray-500">Input</span>
										{item.input_tokens.toLocaleString()}
									</div>
									<div>
										<span class="text-gray-500">Output</span>
										{item.output_tokens.toLocaleString()}
									</div>
									<div>
										<span class="text-gray-500">Cache create</span>
										{(item.cache_creation_tokens ?? 0).toLocaleString()}
									</div>
									<div>
										<span class="text-gray-500">Cache read</span>
										{(item.cache_read_tokens ?? 0).toLocaleString()}
									</div>
									<div>
										<span class="text-gray-500">Plan</span>
										{formatChatpoint(item.plan_cost_micros)} CP
									</div>
									<div>
										<span class="text-gray-500">Check</span>
										{formatChatpoint(item.check_cost_micros)} CP
									</div>
								</div>
								<div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[0.6875rem] text-gray-500">
									<span>First token {formatDuration(item.first_token_latency_ms)}</span>
									<span>Total {formatDuration(item.total_duration_ms)}</span>
									{#if item.unpaid_cost_micros > 0}
										<span class="text-amber-700 dark:text-amber-300"
											>Unpaid {formatChatpoint(item.unpaid_cost_micros)} CP</span
										>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="py-2 text-[0.6875rem] text-gray-500">
						{$i18n.t('No billed requests in this period.')}
					</div>
				{/if}
			</section>

			<section class="mt-4 border-t border-gray-100 pt-4 dark:border-gray-850">
				<h3 class="mb-3 text-[0.6875rem] font-medium text-gray-500">
					{$i18n.t('Recent balance activity')}
				</h3>
				{#if data.ledger.length}
					<div class="divide-y divide-gray-100 dark:divide-gray-850">
						{#each data.ledger.slice(0, 25) as entry}
							<div class="grid grid-cols-[minmax(0,1fr)_auto] gap-4 py-2.5">
								<div class="min-w-0">
									<div class="truncate">{entry.event_type}</div>
									<div class="mt-0.5 text-[0.6875rem] text-gray-500">
										{formatDate(entry.created_at)}
									</div>
								</div>
								<div class="text-right text-[0.6875rem]">
									<div>Plan {formatChatpoint(entry.plan_delta_micros)}</div>
									<div class="mt-0.5 text-gray-500">
										Check {formatChatpoint(entry.check_delta_micros)}
									</div>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<div class="text-[0.6875rem] text-gray-500">{$i18n.t('No balance activity yet.')}</div>
				{/if}
			</section>
		</div>
	{/if}
</div>
