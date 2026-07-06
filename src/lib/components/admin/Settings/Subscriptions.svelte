<script lang="ts">
	import { page } from '$app/stores';
	import Plans from './Subscriptions/Plans.svelte';
	import ModelAccess from './Subscriptions/ModelAccess.svelte';
	import RedeemCodes from './Subscriptions/RedeemCodes.svelte';
	import UserSubscriptions from './Subscriptions/UserSubscriptions.svelte';
	import UsageLedger from './Subscriptions/UsageLedger.svelte';

	let selectedTab = 'plans';
	let appliedUserQuery = '';

	const tabs = [
		{ id: 'plans', label: '订阅计划' },
		{ id: 'model-access', label: '模型权限' },
		{ id: 'redeem-codes', label: '兑换码' },
		{ id: 'user-subscriptions', label: '用户订阅' },
		{ id: 'usage-ledger', label: '用量账本' }
	];

	$: requestedUser = $page.url.searchParams.get('user') ?? '';
	$: if (requestedUser && requestedUser !== appliedUserQuery) {
		selectedTab = 'user-subscriptions';
		appliedUserQuery = requestedUser;
	}
</script>

<div id="admin-subscriptions" class="flex h-full min-h-0 flex-col gap-3 text-sm lg:flex-row">
	<div class="flex gap-1 overflow-x-auto lg:w-44 lg:flex-none lg:flex-col lg:overflow-visible">
		{#each tabs as tab}
			<button
				type="button"
				class="min-w-fit rounded-lg px-2.5 py-1.5 text-left transition {selectedTab === tab.id
					? 'bg-gray-100 font-medium dark:bg-gray-850'
					: 'text-gray-500 hover:text-gray-900 dark:hover:text-gray-100'}"
				on:click={() => {
					selectedTab = tab.id;
				}}
			>
				{tab.label}
			</button>
		{/each}
	</div>

	<div class="min-w-0 flex-1">
		{#if selectedTab === 'plans'}
			<Plans />
		{:else if selectedTab === 'model-access'}
			<ModelAccess />
		{:else if selectedTab === 'redeem-codes'}
			<RedeemCodes />
		{:else if selectedTab === 'user-subscriptions'}
			<UserSubscriptions initialQuery={requestedUser} />
		{:else if selectedTab === 'usage-ledger'}
			<UsageLedger />
		{/if}
	</div>
</div>
