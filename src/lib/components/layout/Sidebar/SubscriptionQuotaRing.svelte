<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { getMySubscription } from '$lib/apis/subscriptions';

	export let showBadge = false;

	const dispatch = createEventDispatcher();
	const CHATPOINT_MICROS = 1_000_000;

	let subscription: any = null;
	let loading = true;

	const clampPercent = (value: number) => Math.max(0, Math.min(100, value));
	const positive = (value: number) => Math.max(0, value);

	const formatChatpoint = (micros?: number | null) => {
		return ((micros ?? 0) / CHATPOINT_MICROS).toLocaleString(undefined, {
			maximumFractionDigits: 2
		});
	};

	const formatDate = (value?: number | null) => {
		if (!value) return '-';
		return new Date(value * 1000).toLocaleDateString();
	};

	onMount(async () => {
		subscription = await getMySubscription(localStorage.token).catch(() => null);
		loading = false;
	});

	$: planRemaining = subscription?.plan_balance_micros ?? 0;
	$: checkRemaining = subscription?.check_balance_micros ?? 0;
	$: planTotal = Math.max(subscription?.plan_chatpoint_allowance_micros ?? 0, 0);
	$: checkTotal = Math.max(
		subscription?.snapshot?.check_chatpoint_allowance_micros ?? 0,
		positive(checkRemaining)
	);
	$: totalRemaining = planRemaining + checkRemaining;
	$: totalAvailable = Math.max(planTotal + checkTotal, positive(totalRemaining), 1);
	$: remainingPercent = clampPercent((positive(totalRemaining) / totalAvailable) * 100);
	$: planPercent = planTotal > 0 ? clampPercent((positive(planRemaining) / planTotal) * 100) : 0;
	$: checkPercent = checkTotal > 0 ? clampPercent((positive(checkRemaining) / checkTotal) * 100) : 0;
	$: exhausted = !loading && totalRemaining <= 0;
	$: low = !exhausted && remainingPercent <= 20;
	$: tier = subscription?.display_name ?? subscription?.tier ?? 'Free';
</script>

<button
	id="subscription-quota-ring"
	class="group relative flex items-center gap-2 rounded-xl px-1.5 py-1 text-left transition hover:bg-gray-100 dark:hover:bg-gray-800"
	type="button"
	on:click|stopPropagation={() => dispatch('openUsage')}
	aria-label="Usage"
>
	<span class="relative flex size-8 items-center justify-center">
		<svg class="size-8 -rotate-90" viewBox="0 0 36 36" aria-label="Usage">
			<circle
				class="text-gray-200 dark:text-gray-800"
				stroke="currentColor"
				stroke-width="4"
				fill="none"
				cx="18"
				cy="18"
				r="15"
			/>
			<circle
				class={exhausted ? 'stroke-red-500' : low ? 'stroke-yellow-500' : 'stroke-green-500'}
				stroke-width="4"
				fill="none"
				cx="18"
				cy="18"
				r="15"
				stroke-dasharray={`${remainingPercent} 100`}
				pathLength="100"
				stroke-linecap="round"
			/>
		</svg>
		<span class="absolute text-[10px] font-semibold uppercase text-gray-700 dark:text-gray-200">
			{loading ? '-' : tier.slice(0, 1)}
		</span>
	</span>

	{#if showBadge}
		<span
			class="max-w-[5.5rem] truncate rounded-full px-2 py-0.5 text-xs font-medium {exhausted
				? 'bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-300'
				: 'bg-gray-100 text-gray-600 dark:bg-gray-850 dark:text-gray-200'}"
		>
			{tier}
		</span>
	{/if}

	<div
		class="pointer-events-none absolute bottom-full right-0 z-50 mb-2 hidden w-64 rounded-xl border border-gray-100 bg-white p-3 text-xs shadow-lg group-hover:block group-focus-visible:block dark:border-gray-800 dark:bg-gray-900"
	>
		<div class="mb-2 flex items-center justify-between gap-2">
			<div class="font-medium text-gray-900 dark:text-gray-100">Usage</div>
			<div
				class="rounded-full px-2 py-0.5 {exhausted
					? 'bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-300'
					: 'bg-gray-100 text-gray-600 dark:bg-gray-850 dark:text-gray-300'}"
			>
				{tier}
			</div>
		</div>

		<div class="space-y-2">
			<div>
				<div class="mb-1 flex justify-between gap-2">
					<span>Plan Chatpoint</span>
					<span>{formatChatpoint(planRemaining)}/{formatChatpoint(planTotal)}</span>
				</div>
				<div class="h-1.5 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
					<div
						class={exhausted ? 'h-full rounded-full bg-red-500' : 'h-full rounded-full bg-green-500'}
						style:width={`${planPercent}%`}
					></div>
				</div>
			</div>

			<div>
				<div class="mb-1 flex justify-between gap-2">
					<span>Check Chatpoint</span>
					<span>{formatChatpoint(checkRemaining)}/{formatChatpoint(checkTotal)}</span>
				</div>
				<div class="h-1.5 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
					<div
						class={exhausted ? 'h-full rounded-full bg-red-500' : 'h-full rounded-full bg-sky-500'}
						style:width={`${checkPercent}%`}
					></div>
				</div>
			</div>
		</div>

		<div class="mt-2 text-[11px] text-gray-500">Next reset: {formatDate(subscription?.next_reset_at)}</div>
	</div>
</button>
