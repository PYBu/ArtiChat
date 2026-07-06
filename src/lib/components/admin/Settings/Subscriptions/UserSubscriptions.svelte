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
	const statusLabel = (status?: string) => {
		if (status === 'active') return '有效';
		if (status === 'expired') return '已过期';
		if (status === 'inactive') return '未启用';
		return status || '-';
	};

	const normalize = (item: any) => {
		const subscription = item.subscription ?? item;
		return {
			...subscription,
			user: item.user ?? null,
			plan_chatpoint: formatChatpoint(subscription.plan_balance_micros),
			check_chatpoint: formatChatpoint(subscription.check_balance_micros),
			expires_at_input: toDateTimeLocal(subscription.expires_at)
		};
	};

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
			Object.assign(row, normalize({ subscription: updated, user: row.user }));
			toast.success('用户订阅已保存。');
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
		<div class="text-base font-medium">用户订阅</div>
		<div class="text-xs text-gray-500">编辑用户订阅档位、到期时间以及剩余周期/充值 Chatpoint。</div>
	</div>

	<div class="flex gap-2">
		<input class="w-full rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850" placeholder="按邮箱、用户名、显示名或用户 ID 搜索" bind:value={query} />
		<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" on:click={load}>
			搜索
		</button>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">暂无用户订阅。</div>
	{:else}
		<div class="flex flex-col gap-2">
			{#each rows as row (row.user_id)}
				<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
					<div class="mb-2 flex items-center justify-between gap-2">
						<div class="min-w-0">
							<div class="truncate font-medium">{row.user?.email ?? row.user_id}</div>
							<div class="truncate text-xs text-gray-500">{row.user?.username ?? row.user?.name ?? row.user_id}</div>
							<div class="text-xs text-gray-500">下次重置：{row.next_reset_at ? new Date(row.next_reset_at * 1000).toLocaleString() : '-'}</div>
						</div>
						<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" on:click={() => save(row)}>
							保存
						</button>
					</div>

					<div class="grid gap-2 md:grid-cols-3">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">订阅档位</span>
							<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.tier}>
								<option value="free">Free</option>
								<option value="plus">Plus</option>
								<option value="chatpower">ChatPower</option>
							</select>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">状态</span>
							<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.status}>
								<option value="active">{statusLabel('active')}</option>
								<option value="expired">{statusLabel('expired')}</option>
								<option value="inactive">{statusLabel('inactive')}</option>
							</select>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">到期时间</span>
							<input type="datetime-local" class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.expires_at_input} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">周期 Chatpoint</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.plan_chatpoint} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">充值 Chatpoint</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.check_chatpoint} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">备注</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.notes} />
						</label>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
