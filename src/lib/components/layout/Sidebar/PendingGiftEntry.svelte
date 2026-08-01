<script lang="ts">
	import { createEventDispatcher, getContext, onDestroy, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';

	import { getPendingGiftCards } from '$lib/apis/subscriptions';
	import Gift from '$lib/components/icons/Gift.svelte';
	import { user } from '$lib/stores';
	import { subscriptionRefreshTick } from '$lib/stores/subscriptions';

	const dispatch = createEventDispatcher<{ redeem: void }>();
	const i18n: Writable<any> = getContext('i18n');

	let hasPendingGift = false;
	let unsubscribe: (() => void) | null = null;

	const load = async () => {
		const token = typeof localStorage !== 'undefined' ? (localStorage.getItem('token') ?? '') : '';
		if (!$user || !token) {
			hasPendingGift = false;
			return;
		}

		const response = await getPendingGiftCards(token).catch(() => ({ items: [] }));
		hasPendingGift = response.items.length > 0;
	};

	onMount(() => {
		unsubscribe = subscriptionRefreshTick.subscribe(() => void load());
	});

	onDestroy(() => unsubscribe?.());
</script>

{#if hasPendingGift}
	<button
		id="pending-gift-entry"
		type="button"
		class="mb-1 flex min-h-[30px] w-full max-w-full items-center gap-2 rounded-lg border border-gray-300 bg-transparent px-2.5 py-1.5 text-left text-xs font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-850"
		on:click={() => dispatch('redeem')}
	>
		<Gift className="size-3.5 shrink-0" />
		{$i18n.t('Claim gift card')}
	</button>
{/if}
