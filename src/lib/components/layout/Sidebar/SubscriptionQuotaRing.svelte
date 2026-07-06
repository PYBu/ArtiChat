<script lang="ts">
	import { createEventDispatcher, onDestroy, onMount } from 'svelte';
	import { refreshSubscription, subscription } from '$lib/stores';

	export let showBadge = false;

	const dispatch = createEventDispatcher();
	const CHATPOINT_MICROS = 1_000_000;

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

	const tierLabel = (tier?: string, displayName?: string) => {
		if (tier === 'free') return 'Free';
		if (tier === 'plus') return 'Plus';
		if (tier === 'chatpower') return 'ChatPower';
		return displayName || tier || 'Free';
	};

	const load = async () => {
		loading = true;
		await refreshSubscription();
		loading = false;
	};

	const handleFocus = () => {
		refreshSubscription();
	};

	onMount(async () => {
		await load();
		window.addEventListener('focus', handleFocus);
	});

	onDestroy(() => {
		window.removeEventListener('focus', handleFocus);
	});

	$: currentSubscription = $subscription;
	$: planRemaining = currentSubscription?.plan_balance_micros ?? 0;
	$: checkRemaining = currentSubscription?.check_balance_micros ?? 0;
	$: planTotal = Math.max(currentSubscription?.plan_chatpoint_allowance_micros ?? 0, 0);
	$: checkTotal = Math.max(
		currentSubscription?.snapshot?.check_chatpoint_allowance_micros ?? 0,
		positive(checkRemaining)
	);
	$: totalRemaining = planRemaining + checkRemaining;
	$: totalAvailable = Math.max(planTotal + checkTotal, positive(totalRemaining), 1);
	$: remainingPercent = clampPercent((positive(totalRemaining) / totalAvailable) * 100);
	$: planPercent = planTotal > 0 ? clampPercent((positive(planRemaining) / planTotal) * 100) : 0;
	$: checkPercent = checkTotal > 0 ? clampPercent((positive(checkRemaining) / checkTotal) * 100) : 0;
	$: exhausted = !loading && totalRemaining <= 0;
	$: low = !exhausted && remainingPercent <= 20;
	$: tier = tierLabel(currentSubscription?.tier, currentSubscription?.display_name);
</script>

<button
	id="subscription-quota-ring"
	class="group relative flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-left transition hover:bg-gray-100 dark:hover:bg-gray-800"
	type="button"
	on:click|stopPropagation={() => dispatch('openUsage')}
	aria-label="用量 / Usage"
>
	<span class="max-w-[4.5rem] truncate text-[11px] font-medium text-gray-600 dark:text-gray-200">
		{tier}
	</span>

	<span class="relative flex size-6 items-center justify-center">
		<svg class="size-6 -rotate-90" viewBox="0 0 36 36" aria-label="用量 / Usage">
			<circle
				class="text-gray-200 dark:text-gray-800"
				stroke="currentColor"
				stroke-width="2.5"
				fill="none"
				cx="18"
				cy="18"
				r="15"
			/>
			<circle
				class={exhausted ? 'stroke-red-500' : low ? 'stroke-yellow-500' : 'stroke-green-500'}
				stroke-width="2.5"
				fill="none"
				cx="18"
				cy="18"
				r="15"
				stroke-dasharray={`${remainingPercent} 100`}
				pathLength="100"
				stroke-linecap="round"
			/>
		</svg>
	</span>

	<div
		class="pointer-events-none absolute bottom-full right-0 z-50 mb-2 hidden w-72 rounded-xl border border-gray-100 bg-white p-3 text-xs shadow-lg group-hover:block group-focus-visible:block dark:border-gray-800 dark:bg-gray-900"
	>
		<div class="mb-2 flex items-center justify-between gap-2">
			<div class="font-medium text-gray-900 dark:text-gray-100">用量 / Usage</div>
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
				<div class="h-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
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
				<div class="h-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
					<div
						class={exhausted ? 'h-full rounded-full bg-red-500' : 'h-full rounded-full bg-sky-500'}
						style:width={`${checkPercent}%`}
					></div>
				</div>
			</div>
		</div>

		<div class="mt-2 text-[11px] text-gray-500">下次重置：{formatDate(currentSubscription?.next_reset_at)}</div>
	</div>
</button>
