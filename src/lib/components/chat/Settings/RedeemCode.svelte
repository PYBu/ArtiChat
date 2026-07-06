<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { redeemSubscriptionCode } from '$lib/apis/subscriptions';

	const dispatch = createEventDispatcher();
	let code = '';
	let result: any = null;
	let error = '';
	let loading = false;

	const formatChatpoint = (micros?: number | null) => {
		return ((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 6 });
	};

	const redeem = async () => {
		if (!code.trim() || loading) return;
		loading = true;
		error = '';
		result = null;
		try {
			result = await redeemSubscriptionCode(localStorage.token, code.trim());
			code = '';
			toast.success('Code redeemed.');
			dispatch('redeemed');
		} catch (err) {
			error = `${err}`;
			toast.error(error);
		}
		loading = false;
	};
</script>

<div id="tab-redeem-code" class="flex h-full flex-col gap-4 text-sm">
	<div class="text-base font-medium">Redeem Code</div>
	<div class="flex gap-2">
		<input class="w-full rounded-lg border border-gray-100 bg-transparent px-3 py-2 outline-hidden dark:border-gray-850" bind:value={code} />
		<button class="rounded-full bg-black px-4 py-2 text-white dark:bg-white dark:text-black" type="button" on:click={redeem}>
			{loading ? 'Redeeming' : 'Redeem'}
		</button>
	</div>

	{#if error}
		<div class="rounded-lg border border-red-200 p-3 text-red-600 dark:border-red-900">{error}</div>
	{/if}

	{#if result}
		<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
			<div class="font-medium">{result.tier_after ?? result.subscription?.tier}</div>
			<div class="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-300">
				<div>Plan Chatpoint</div>
				<div class="text-right">{formatChatpoint(result.plan_delta_micros)}</div>
				<div>Check Chatpoint</div>
				<div class="text-right">{formatChatpoint(result.check_delta_micros)}</div>
			</div>
		</div>
	{/if}
</div>
