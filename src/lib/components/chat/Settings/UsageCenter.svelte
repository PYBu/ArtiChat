<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';

	import ActivityUsage from './Usage.svelte';
	import SubscriptionUsage from './SubscriptionUsage.svelte';

	const i18n: Writable<any> = getContext('i18n');
	type UsageView = 'billing' | 'activity';

	let view: UsageView = 'billing';
</script>

<div class="flex h-full min-h-0 flex-col">
	<div class="mb-4 flex shrink-0 items-center justify-between gap-3">
		<h2 class="text-sm font-medium text-gray-900 dark:text-white">{$i18n.t('Usage')}</h2>
		<div
			class="flex shrink-0 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-850"
			role="tablist"
			aria-label={$i18n.t('Usage')}
		>
			<button
				type="button"
				role="tab"
				aria-selected={view === 'billing'}
				class="h-7 rounded-md px-2.5 text-xs transition {view === 'billing'
					? 'bg-white font-medium text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white'
					: 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}"
				on:click={() => (view = 'billing')}
			>
				{$i18n.t('Chatpoint Billing')}
			</button>
			<button
				type="button"
				role="tab"
				aria-selected={view === 'activity'}
				class="h-7 rounded-md px-2.5 text-xs transition {view === 'activity'
					? 'bg-white font-medium text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white'
					: 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}"
				on:click={() => (view = 'activity')}
			>
				{$i18n.t('Activity')}
			</button>
		</div>
	</div>

	<div class="min-h-0 flex-1">
		{#if view === 'billing'}
			<SubscriptionUsage />
		{:else}
			<ActivityUsage />
		{/if}
	</div>
</div>
