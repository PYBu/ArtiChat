<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Modal from '$lib/components/common/Modal.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import { searchUsers } from '$lib/apis/users';
	import {
		createAdminGiftCards,
		getAdminGiftCards,
		revokeAdminGiftCard,
		type AdminGiftCard,
		type UserSummary
	} from '$lib/apis/subscriptions';

	type BenefitType = 'subscription' | 'recharge';
	let rows: AdminGiftCard[] = [];
	let loading = true;
	let creating = false;
	let recipientOpen = false;
	let selectedUsers: UserSummary[] = [];
	let userQuery = '';
	let userResults: UserSummary[] = [];
	let searchingUsers = false;
	let userSearchComplete = false;
	let userSearchTimer: ReturnType<typeof setTimeout>;
	let userSearchSequence = 0;
	let benefitTab: BenefitType = 'subscription';

	let form = {
		all_users: false,
		benefit_type: 'subscription' as BenefitType,
		tier: 'plus',
		duration_days: 30,
		plan_chatpoint: 100,
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
	const benefitLabel = (type?: string | null) => (type === 'recharge' ? '额度充值卡' : '订阅卡');
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

	$: form.benefit_type = benefitTab;
	$: recipientSummary = form.all_users
		? '当前所有用户'
		: selectedUsers.length
			? `已选择 ${selectedUsers.length} 位用户`
			: '请选择收件用户';

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
		if (!selectedUsers.some((selected) => selected.id === user.id))
			selectedUsers = [...selectedUsers, user];
		userQuery = '';
		userResults = [];
		userSearchComplete = false;
	};

	const removeUser = (userId: string) => {
		selectedUsers = selectedUsers.filter((user) => user.id !== userId);
	};

	const chooseRecipientMode = (allUsers: boolean) => {
		form.all_users = allUsers;
		userQuery = '';
		userResults = [];
		userSearchComplete = false;
		userSearchSequence += 1;
	};

	const openRecipientWindow = () => {
		recipientOpen = true;
	};

	const confirmRecipient = () => {
		if (!form.all_users && selectedUsers.length === 0) {
			toast.error('请至少选择一位用户。');
			return;
		}
		recipientOpen = false;
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
			toast.error('请先选择收件用户。');
			return;
		}

		creating = true;
		const isSubscription = form.benefit_type === 'subscription';
		const created = await createAdminGiftCards(localStorage.token, {
			all_users: form.all_users,
			user_ids,
			mode: 'single_use',
			benefit_type: form.benefit_type,
			tier: isSubscription ? form.tier || null : null,
			duration_days: isSubscription ? Number(form.duration_days) : null,
			plan_chatpoint: isSubscription ? form.plan_chatpoint : 0,
			check_chatpoint: isSubscription ? 0 : form.check_chatpoint,
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
			form.memo = '';
			await load();
		}
		creating = false;
	};

	const revoke = async (grantId: string) => {
		if (!window.confirm('撤销后该礼品卡将无法领取，继续吗？')) return;
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

<div class="admin-operations flex flex-col gap-4">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div>
			<div class="text-base font-medium">礼品卡</div>
			<div class="text-xs text-gray-500">向指定用户或当前所有用户发放待领取权益。</div>
		</div>
	</div>

	<div
		class="rounded-lg border border-gray-100/60 bg-white/40 p-3 dark:border-white/[0.06] dark:bg-white/[0.02]"
	>
		<div class="mb-3 flex flex-wrap gap-1 rounded-lg bg-gray-50/70 p-1 dark:bg-white/[0.04]">
			{#each [['subscription', '订阅卡'], ['recharge', '额度充值卡']] as [value, label]}
				<button
					type="button"
					class:font-medium={benefitTab === value}
					class:bg-white={benefitTab === value}
					class:shadow-sm={benefitTab === value}
					class="rounded-md px-3 py-1.5 text-xs text-gray-600 dark:text-gray-300"
					on:click={() => (benefitTab = value as BenefitType)}>{label}</button
				>
			{/each}
		</div>
		<div class="grid gap-3 md:grid-cols-3">
			<div class="flex min-w-0 flex-col gap-1 md:col-span-2">
				<span class="text-xs text-gray-500">收件对象</span>
				<button
					type="button"
					class="flex h-7 w-full items-center justify-between rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-left text-xs text-gray-700 hover:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
					on:click={openRecipientWindow}
				>
					<span class:font-medium={form.all_users || selectedUsers.length > 0}
						>{recipientSummary}</span
					>
					<span class="text-gray-400">选择</span>
				</button>
			</div>
			{#if benefitTab === 'subscription'}
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">订阅档位</span>
					<select
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.tier}
					>
						<option value="plus">Plus</option>
						<option value="chatpower">ChatPower</option>
						<option value="free">Free</option>
					</select>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">订阅天数</span>
					<input
						type="number"
						min="1"
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.duration_days}
					/>
				</label>
			{:else}
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">充值额度</span>
					<input
						type="number"
						min="0"
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.check_chatpoint}
					/>
				</label>
			{/if}
			<label class="flex flex-col gap-1 md:col-span-2">
				<span class="text-xs text-gray-500">备注</span>
				<input
					class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
					bind:value={form.memo}
				/>
			</label>
		</div>
		<div class="mt-3 flex justify-end">
			<button
				type="button"
				class="rounded-lg bg-black px-3 py-1.5 text-xs font-medium text-white transition hover:bg-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black"
				disabled={creating || (!form.all_users && selectedUsers.length === 0)}
				on:click={create}>{creating ? '发放中...' : '发放礼品卡'}</button
			>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div
			class="rounded-lg border border-gray-100/60 bg-gray-50/30 p-3 text-xs text-gray-500 dark:border-white/[0.06] dark:bg-white/[0.02]"
		>
			暂无礼品卡。
		</div>
	{:else}
		<div class="grid gap-2">
			{#each rows as row (row.grant.id)}
				<div
					class="rounded-lg border border-gray-100/60 bg-white/40 p-3 text-xs dark:border-white/[0.06] dark:bg-white/[0.02]"
				>
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div class="min-w-0">
							<div class="font-medium">{benefitLabel(row.code?.benefit_type)}</div>
							<div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-gray-500">
								{#if row.code?.benefit_type === 'subscription'}<span
										>{tierLabel(row.code?.tier)} · {row.code?.duration_days ?? 0} 天</span
									>{/if}
								{#if row.code?.benefit_type === 'recharge'}<span
										>{formatChatpoint(row.code?.check_chatpoint_micros)} CP</span
									>{/if}
								<span>{userLabel(row)}</span><span>{formatDate(row.grant.created_at)}</span>
							</div>
						</div>
						<div class="flex shrink-0 items-center gap-2">
							<span
								class="rounded-md bg-gray-50 px-2 py-1 text-[11px] text-gray-600 dark:bg-white/[0.05] dark:text-gray-300"
								>{statusLabel(row.grant.status)}</span
							>
							{#if row.grant.status === 'pending'}<button
									type="button"
									class="rounded-lg border border-red-200/70 px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 dark:border-red-900/60 dark:text-red-300"
									on:click={() => revoke(row.grant.id)}>撤销</button
								>{/if}
						</div>
					</div>
					{#if row.grant.memo}<div class="mt-2 text-gray-500">{row.grant.memo}</div>{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<Modal
	bind:show={recipientOpen}
	size="md"
	closeOnBackdrop={false}
	closeOnEscape={false}
	className="rounded-lg bg-white dark:bg-gray-900"
>
	<div class="flex max-h-[80vh] flex-col">
		<div
			class="flex items-start justify-between border-b border-gray-100/70 p-4 dark:border-white/[0.06]"
		>
			<div>
				<div class="text-sm font-medium">选择发放对象</div>
				<div class="mt-1 text-[11px] text-gray-500">全体用户和指定用户只能选择一种。</div>
			</div>
			<button
				type="button"
				class="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-white/[0.06]"
				aria-label="关闭"
				on:click={() => (recipientOpen = false)}
				><XMark className="size-4" strokeWidth="2" /></button
			>
		</div>
		<div class="min-h-0 overflow-y-auto p-4">
			<div class="mb-3 flex gap-1 rounded-lg bg-gray-50/70 p-1 dark:bg-white/[0.04]">
				<button
					type="button"
					class:font-medium={form.all_users}
					class:bg-white={form.all_users}
					class:shadow-sm={form.all_users}
					class="flex-1 rounded-md px-3 py-1.5 text-xs text-gray-600 dark:text-gray-300"
					on:click={() => chooseRecipientMode(true)}>当前所有用户</button
				>
				<button
					type="button"
					class:font-medium={!form.all_users}
					class:bg-white={!form.all_users}
					class:shadow-sm={!form.all_users}
					class="flex-1 rounded-md px-3 py-1.5 text-xs text-gray-600 dark:text-gray-300"
					on:click={() => chooseRecipientMode(false)}>指定用户</button
				>
			</div>
			{#if form.all_users}
				<div
					class="rounded-lg border border-amber-200/70 bg-amber-50/50 p-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-200"
				>
					发放会覆盖当前所有 user/admin 账号，不包含未来注册用户。
				</div>
			{:else}
				{#if selectedUsers.length > 0}
					<div class="mb-2 flex flex-wrap gap-1">
						{#each selectedUsers as user (user.id)}
							<div
								class="flex max-w-full items-center gap-1 rounded-md border border-gray-100/60 bg-gray-50/50 px-2 py-1 text-xs dark:border-white/[0.06] dark:bg-white/[0.03]"
							>
								<span class="max-w-48 truncate">{selectedUserLabel(user)}</span>
								<button
									type="button"
									class="shrink-0 text-gray-500 hover:text-gray-900 dark:hover:text-white"
									aria-label={`移除 ${selectedUserLabel(user)}`}
									on:click={() => removeUser(user.id)}
									><XMark className="size-3.5" strokeWidth="2" /></button
								>
							</div>
						{/each}
					</div>
				{/if}
				<div class="relative">
					<input
						class="h-8 w-full rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						placeholder="输入姓名、邮箱或用户名搜索"
						autocomplete="off"
						bind:value={userQuery}
						on:input={scheduleUserSearch}
					/>
					{#if userQuery.trim()}
						<div
							class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-100/60 bg-white py-1 dark:border-white/[0.06] dark:bg-gray-900"
						>
							{#if searchingUsers}<div class="px-3 py-2 text-xs text-gray-500">
									搜索中...
								</div>{:else if userResults.length > 0}{#each userResults as user (user.id)}<button
										type="button"
										class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-white/[0.05]"
										on:click={() => selectUser(user)}
										><span class="min-w-0"
											><span class="block truncate text-sm font-medium"
												>{selectedUserLabel(user)}</span
											><span class="block truncate text-xs text-gray-500"
												>{user.email ?? '未设置邮箱'}</span
											></span
										>{#if user.username}<span
												class="max-w-36 shrink-0 truncate text-xs text-gray-500"
												>@{user.username}</span
											>{/if}</button
									>{/each}{:else if userSearchComplete}<div class="px-3 py-2 text-xs text-gray-500">
									未找到匹配用户
								</div>{/if}
						</div>
					{/if}
				</div>
			{/if}
		</div>
		<div class="flex justify-end gap-2 border-t border-gray-100/70 p-4 dark:border-white/[0.06]">
			<button
				type="button"
				class="rounded-lg border border-gray-200/70 px-3 py-1.5 text-xs text-gray-600 dark:border-white/[0.08] dark:text-gray-300"
				on:click={() => (recipientOpen = false)}>取消</button
			>
			<button
				type="button"
				class="rounded-lg bg-black px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black"
				disabled={!form.all_users && selectedUsers.length === 0}
				on:click={confirmRecipient}>确认对象</button
			>
		</div>
	</div>
</Modal>

<style>
	.admin-operations :global(.text-base.font-medium) {
		font-size: 0.875rem;
		line-height: 1.25rem;
	}

	.admin-operations :global(.text-xs.text-gray-500) {
		font-size: 0.6875rem;
		line-height: 1rem;
	}
</style>
