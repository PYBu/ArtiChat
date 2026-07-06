<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { redeemSubscriptionCode } from '$lib/apis/subscriptions';

	const dispatch = createEventDispatcher();
	let code = '';

	const redeem = async () => {
		if (!code.trim()) return;
		await redeemSubscriptionCode(localStorage.token, code.trim());
		code = '';
		dispatch('redeemed');
	};
</script>

<div id="tab-redeem-code" class="flex h-full flex-col gap-3 text-sm">
	<div class="text-base font-medium">Redeem Code</div>
	<div class="flex gap-2">
		<input class="w-full rounded border px-3 py-2 dark:bg-gray-900" bind:value={code} />
		<button class="rounded bg-black px-3 py-2 text-white dark:bg-white dark:text-black" type="button" on:click={redeem}>
			Redeem
		</button>
	</div>
</div>
