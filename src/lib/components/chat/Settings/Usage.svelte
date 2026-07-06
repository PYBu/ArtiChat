<script lang="ts">
	import { onMount } from 'svelte';
	import { getMySubscriptionUsage } from '$lib/apis/subscriptions';

	let usage: any = null;

	onMount(async () => {
		usage = await getMySubscriptionUsage(localStorage.token).catch(() => null);
	});
</script>

<div id="tab-usage" class="flex h-full flex-col text-sm">
	<div class="text-base font-medium">Usage</div>
	{#if usage?.subscription}
		<div class="mt-3">{usage.subscription.tier}</div>
	{/if}
</div>
