<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		getAdminUserSubscriptions,
		updateAdminUserSubscription
	} from '$lib/apis/subscriptions';

	export let initialQuery = '';

	let query = initialQuery;
	let rows: any[] = [];
	let loading = true;
	let lastLoadedQuery = '';

	const formatChatpoint = (micros?: number | null) => `${(micros ?? 0) / 1_000_000}`;
	const toDateTimeLocal = (value?: number | null) => {
		if (!value) return '';
		const date = new Date(value * 1000);
		date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
		return date.toISOString().slice(0, 16);
	};
	const fromDateTimeLocal = (value: string) => {
		return value ? Math.floor(new Date(value).getTime() / 1000) : null;
	};

	const normalize = (subscription: any) => ({
		...subscription,
		plan_chatpoint: formatChatpoint(subscription.plan_balance_micros),
		check_chatpoint: formatChatpoint(subscription.check_balance_micros),
		expires_at_input: toDateTimeLocal(subscription.expires_at)
	});

	const load = async () => {
		loading = true;
		lastLoadedQuery = query;
		const response = await getAdminUserSubscriptions(localStorage.token, query).catch((error) => {
			toast.error(`${error}`);
			return { items: [] };
		});
		rows = (response?.items ?? []).map(normalize);
		loading = false;
	};

	const save = async (row: any) => {
		const updated = await updateAdminUserSubscription(localStorage.token, row.user_id, {
			tier: row.tier,
			expires_at: fromDateTimeLocal(row.expires_at_input),
			plan_chatpoint: row.plan_chatpoint,
			check_chatpoint: row.check_chatpoint,
			status: row.status,
			notes: row.notes ?? null
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (updated) {
			Object.assign(row, normalize(updated));
			toast.success('User subscription saved.');
		}
	};

	$: if (initialQuery && initialQuery !== query && initialQuery !== lastLoadedQuery) {
		query = initialQuery;
		load();
	}

	onMount(load);
</script>

<div class="flex flex-col gap-3">
	<div>
		<div class="text-base font-medium">User Subscriptions</div>
		<div class="text-xs text-gray-500">Edit a user tier, expiry, and remaining Plan/Check Chatpoint.</div>
	</div>

	<div class="flex gap-2">
		<input class="w-full rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850" placeholder="Search by user id" bind:value={query} />
		<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" on:click={load}>
			Search
		</button>
	</div>

	{#if loading}
		<div class="text-gray-500">Loading...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">No user subscriptions.</div>
	{:else}
		<div class="flex flex-col gap-2">
			{#each rows as row (row.user_id)}
				<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
					<div class="mb-2 flex items-center justify-between gap-2">
						<div class="min-w-0">
							<div class="truncate font-medium">{row.user_id}</div>
							<div class="text-xs text-gray-500">Next reset: {row.next_reset_at ? new Date(row.next_reset_at * 1000).toLocaleString() : '-'}</div>
						</div>
						<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" on:click={() => save(row)}>
							Save
						</button>
					</div>

					<div class="grid gap-2 md:grid-cols-3">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">Tier</span>
							<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.tier}>
								<option value="free">Free</option>
								<option value="plus">Plus</option>
								<option value="chatpower">ChatPower</option>
							</select>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">Status</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.status} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">Expires At</span>
							<input type="datetime-local" class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.expires_at_input} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">Plan Chatpoint</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.plan_chatpoint} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">Check Chatpoint</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.check_chatpoint} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">Notes</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.notes} />
						</label>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
