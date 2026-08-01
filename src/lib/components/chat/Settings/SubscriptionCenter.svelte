<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import RedeemCode from './RedeemCode.svelte';
	import Subscription from './Subscription.svelte';
	import SubscriptionUsage from './SubscriptionUsage.svelte';

	type Tab = 'overview' | 'usage' | 'redeem';
	let tab: Tab = 'overview';

	const tabs: Array<{ id: Tab; label: string }> = [
		{ id: 'overview', label: 'Subscription' },
		{ id: 'usage', label: 'Billing usage' },
		{ id: 'redeem', label: 'Redeem' }
	];

	$: requestedTab = $page.url.searchParams.get('tab');
	$: if (requestedTab && tabs.some((item) => item.id === requestedTab) && requestedTab !== tab) {
		tab = requestedTab as Tab;
	}

	const selectTab = async (nextTab: Tab) => {
		tab = nextTab;
		const params = new URLSearchParams($page.url.searchParams);
		if (nextTab === 'overview') params.delete('tab');
		else params.set('tab', nextTab);
		const query = params.toString();
		await goto(`${$page.url.pathname}${query ? `?${query}` : ''}`, {
			replaceState: true,
			noScroll: true,
			keepFocus: true
		});
	};
</script>

<div class="mx-auto flex w-full max-w-6xl flex-col px-4 py-5 sm:px-6">
	<header class="border-b border-gray-100 pb-4 dark:border-gray-850">
		<h1 class="text-sm font-medium text-gray-900 dark:text-white">Subscription center</h1>
		<p class="mt-1 text-[0.6875rem] text-gray-500 dark:text-gray-400">
			Manage your plan, Chatpoint balance, usage and gift cards.
		</p>
		<nav
			class="mt-3 inline-flex w-fit max-w-full items-center gap-0.5 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900"
			aria-label="Subscription center sections"
		>
			{#each tabs as item}
				<button
					type="button"
					class="h-7 rounded-md px-2.5 text-[0.6875rem] transition {tab === item.id
						? 'bg-white font-medium text-gray-900 dark:bg-gray-800 dark:text-white'
						: 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}"
					on:click={() => selectTab(item.id)}
				>
					{item.label}
				</button>
			{/each}
		</nav>
	</header>

	<div class="pt-5">
		{#if tab === 'overview'}
			<Subscription on:redeem={() => selectTab('redeem')} />
		{:else if tab === 'usage'}
			<SubscriptionUsage />
		{:else}
			<RedeemCode on:redeemed={() => selectTab('overview')} />
		{/if}
	</div>
</div>
