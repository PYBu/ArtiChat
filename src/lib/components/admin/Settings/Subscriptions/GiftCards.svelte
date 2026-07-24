<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { searchUsers } from '$lib/apis/users';
	import {
		createAdminGiftCards,
		getAdminGiftCards,
		revokeAdminGiftCard,
		type AdminGiftCard,
		type UserSummary
	} from '$lib/apis/subscriptions';
	import XMark from '$lib/components/icons/XMark.svelte';

	let rows: AdminGiftCard[] = [];
	let loading = true;
	let creating = false;
	let selectedUsers: UserSummary[] = [];
	let userQuery = '';
	let userResults: UserSummary[] = [];
	let searchingUsers = false;
	let userSearchComplete = false;
	let userSearchTimer: ReturnType<typeof setTimeout>;
	let userSearchSequence = 0;

	let form = {
		all_users: false,
		tier: '',
		duration_days: 30,
		plan_chatpoint: 0,
		check_chatpoint: 100,
		memo: ''
	};

	const formatDate = (value?: number | null) =>
		value ? new Date(value * 1000).toLocaleString() : '-';
	const formatChatpoint = (micros?: number | null) => ((micros ?? 0) / 1_000_000).toLocaleString();
	const tierLabel = (tier?: string | null) => {
		if (!tier) return '不变更订阅';
		if (tier === 'free') return 'Free';
		if (tier === 'plus') return 'Plus';
		if (tier === 'chatpower') return 'ChatPower';
		return tier;
	};
	const statusLabel = (status?: string) => {
		if (status === 'pending') return '待领取';
		if (status === 'claimed') return '已领取';
		if (status === 'revoked') return '已撤销';
		return status ?? '-';
	};
	const userLabel = (row: AdminGiftCard) =>
		row.user?.email ?? row.user?.username ?? row.grant.user_id ?? '-';
	const selectedUserLabel = (user: UserSummary) =>
		user.name || user.username || user.email || user.id;

	const searchGiftCardUsers = async () => {
		const query = userQuery.trim();
		const sequence = ++userSearchSequence;
		if (!query || form.all_users) {
			userResults = [];
			searchingUsers = false;
			userSearchComplete = false;
			return;
		}

		searchingUsers = true;
		userSearchComplete = false;
		const response = await searchUsers(localStorage.token, query, 'name', 'asc', 1).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);
		if (sequence !== userSearchSequence) return;

		const selectedIds = new Set(selectedUsers.map((user) => user.id));
		userResults = (response?.users ?? [])
			.filter((user: UserSummary) => !selectedIds.has(user.id))
			.slice(0, 8);
		searchingUsers = false;
		userSearchComplete = true;
	};

	const scheduleUserSearch = () => {
		clearTimeout(userSearchTimer);
		userSearchTimer = setTimeout(searchGiftCardUsers, 250);
	};

	const selectUser = (user: UserSummary) => {
		userSearchSequence += 1;
		if (!selectedUsers.some((selected) => selected.id === user.id)) {
			selectedUsers = [...selectedUsers, user];
		}
		userQuery = '';
		userResults = [];
		userSearchComplete = false;
	};

	const removeUser = (userId: string) => {
		selectedUsers = selectedUsers.filter((user) => user.id !== userId);
	};

	const handleAllUsersChange = () => {
		clearTimeout(userSearchTimer);
		userSearchSequence += 1;
		userQuery = '';
		userResults = [];
		userSearchComplete = false;
	};

	const load = async () => {
		loading = true;
		const response = await getAdminGiftCards(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return { items: [] };
		});
		rows = response?.items ?? [];
		loading = false;
	};

	const create = async () => {
		const user_ids = selectedUsers.map((user) => user.id);
		if (!form.all_users && user_ids.length === 0) {
			toast.error('请至少选择一位用户。');
			return;
		}

		creating = true;
		const created = await createAdminGiftCards(localStorage.token, {
			all_users: form.all_users,
			user_ids,
			mode: 'single_use',
			tier: form.tier || null,
			duration_days: Number(form.duration_days),
			plan_chatpoint: form.plan_chatpoint,
			check_chatpoint: form.check_chatpoint,
			memo: form.memo || null
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (created) {
			toast.success('礼品卡已发放。');
			selectedUsers = [];
			userQuery = '';
			userResults = [];
			await load();
		}
		creating = false;
	};

	const revoke = async (grantId: string) => {
		const revoked = await revokeAdminGiftCard(localStorage.token, grantId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (revoked) {
			toast.success('礼品卡已撤销。');
			await load();
		}
	};

	onMount(load);
	onDestroy(() => clearTimeout(userSearchTimer));
</script>

<div class="flex flex-col gap-4">
	<div>
		<div class="text-base font-medium">礼品卡</div>
		<div class="text-xs text-gray-500">给指定用户或当前全体用户发放待领取兑换码。</div>
	</div>

	<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
		<div class="grid gap-2 md:grid-cols-4">
			<label class="flex items-end gap-2 pb-1">
				<input type="checkbox" bind:checked={form.all_users} on:change={handleAllUsersChange} />
				<span>发放给全体用户</span>
			</label>
			<div class="flex min-w-0 flex-col gap-1 md:col-span-3">
				<span class="text-xs text-gray-500">指定用户</span>
				{#if selectedUsers.length > 0}
					<div class="flex flex-wrap gap-1">
						{#each selectedUsers as user (user.id)}
							<div
								class="flex max-w-full items-center gap-1.5 rounded-md bg-gray-100 px-2 py-1 text-xs dark:bg-gray-850"
							>
								<span class="max-w-40 truncate font-medium">{selectedUserLabel(user)}</span>
								{#if user.email && user.email !== selectedUserLabel(user)}
									<span class="max-w-48 truncate text-gray-500">{user.email}</span>
								{/if}
								<button
									type="button"
									class="shrink-0 text-gray-500 hover:text-gray-900 disabled:opacity-40 dark:hover:text-white"
									aria-label={`移除 ${selectedUserLabel(user)}`}
									disabled={form.all_users}
									on:click={() => removeUser(user.id)}
								>
									<XMark className="size-3.5" strokeWidth="2" />
								</button>
							</div>
						{/each}
					</div>
				{/if}

				<div class="relative">
					<input
						class="w-full rounded-lg border border-gray-100 bg-transparent px-2 py-1 disabled:text-gray-400 dark:border-gray-850"
						placeholder="输入姓名或邮箱搜索"
						aria-label="搜索礼品卡接收用户"
						autocomplete="off"
						disabled={form.all_users}
						bind:value={userQuery}
						on:input={scheduleUserSearch}
					/>

					{#if !form.all_users && userQuery.trim()}
						<div
							class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-100 bg-white py-1 shadow-lg dark:border-gray-850 dark:bg-gray-900"
						>
							{#if searchingUsers}
								<div class="px-3 py-2 text-xs text-gray-500">搜索中...</div>
							{:else if userResults.length > 0}
								{#each userResults as user (user.id)}
									<button
										type="button"
										class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-850"
										on:click={() => selectUser(user)}
									>
										<span class="min-w-0">
											<span class="block truncate text-sm font-medium"
												>{selectedUserLabel(user)}</span
											>
											<span class="block truncate text-xs text-gray-500"
												>{user.email ?? '未设置邮箱'}</span
											>
										</span>
										{#if user.username}
											<span class="max-w-36 shrink-0 truncate text-xs text-gray-500"
												>@{user.username}</span
											>
										{/if}
									</button>
								{/each}
							{:else if userSearchComplete}
								<div class="px-3 py-2 text-xs text-gray-500">未找到匹配用户</div>
							{/if}
						</div>
					{/if}
				</div>
			</div>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">订阅档位</span>
				<select
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.tier}
				>
					<option value="">不变更订阅</option>
					<option value="free">Free</option>
					<option value="plus">Plus</option>
					<option value="chatpower">ChatPower</option>
				</select>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">订阅天数</span>
				<input
					type="number"
					min="0"
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.duration_days}
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">周期 Chatpoint</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.plan_chatpoint}
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">充值 Chatpoint</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.check_chatpoint}
				/>
			</label>
			<label class="flex flex-col gap-1 md:col-span-4">
				<span class="text-xs text-gray-500">备注</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.memo}
				/>
			</label>
		</div>
		<div class="mt-3 flex justify-end">
			<button
				type="button"
				class="rounded-full bg-black px-3 py-1.5 text-white disabled:opacity-40 dark:bg-white dark:text-black"
				disabled={creating || (!form.all_users && selectedUsers.length === 0)}
				on:click={create}
			>
				{creating ? '发放中' : '发放礼品卡'}
			</button>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">
			暂无礼品卡。
		</div>
	{:else}
		<div
			class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850"
		>
			{#each rows as row}
				<div class="grid gap-2 p-3 text-xs md:grid-cols-[1fr_7rem_8rem_7rem_8rem_auto]">
					<div class="min-w-0">
						<div class="truncate font-medium">{userLabel(row)}</div>
						<div class="truncate text-gray-500">批次：{row.grant?.batch_id}</div>
					</div>
					<div>{statusLabel(row.grant?.status)}</div>
					<div>{tierLabel(row.code?.tier)}，{row.code?.duration_days ?? 0} 天</div>
					<div>
						{formatChatpoint(
							(row.code?.plan_chatpoint_micros ?? 0) + (row.code?.check_chatpoint_micros ?? 0)
						)} CP
					</div>
					<div>{formatDate(row.grant?.created_at)}</div>
					<div class="text-right">
						{#if row.grant?.status === 'pending'}
							<button
								type="button"
								class="rounded-full px-3 py-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
								on:click={() => revoke(row.grant.id)}
							>
								撤销
							</button>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
