<script lang="ts">
	import { onMount } from 'svelte';
	import { getMySubscription } from '$lib/apis/subscriptions';

	let subscription: any = null;

	onMount(async () => {
		subscription = await getMySubscription(localStorage.token).catch(() => null);
	});
</script>

<div id="tab-subscription" class="flex h-full flex-col text-sm">
	<div class="text-base font-medium">Subscription</div>
	{#if subscription}
		<div class="mt-3">{subscription.display_name ?? subscription.tier}</div>
	{/if}
</div>
