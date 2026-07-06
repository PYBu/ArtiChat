<script lang="ts">
	import { onMount } from 'svelte';
	import { getAdminSubscriptionPlans } from '$lib/apis/subscriptions';

	let plans: any[] = [];

	onMount(async () => {
		plans = (await getAdminSubscriptionPlans(localStorage.token).catch(() => [])) ?? [];
	});
</script>

<div id="admin-subscriptions" class="flex flex-col gap-3 text-sm">
	<div class="text-base font-medium">Subscriptions</div>
	{#each plans as plan}
		<div class="rounded border px-3 py-2">{plan.display_name ?? plan.id}</div>
	{/each}
</div>
