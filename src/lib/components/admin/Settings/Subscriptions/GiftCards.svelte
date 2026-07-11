<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { createAdminGiftCards, getAdminGiftCards, revokeAdminGiftCard } from '$lib/apis/subscriptions';

	let rows: any[] = [];
	let loading = true;
	let creating = false;

	let form = {
		all_users: false,
		user_ids_text: '',
		tier: '',
		duration_days: 30,
		plan_chatpoint: 0,
		check_chatpoint: 100,
		memo: ''
	};

	const formatDate = (value?: number | null) => (value ? new Date(value * 1000).toLocaleString() : '-');
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
	const userLabel = (row: any) => row?.user?.email ?? row?.user?.username ?? row?.grant?.user_id ?? '-';

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
		creating = true;
		const user_ids = form.user_ids_text
			.split(/[\n,，\s]+/)
			.map((item) => item.trim())
			.filter(Boolean);
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
			form.user_ids_text = '';
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
</script>

<div class="flex flex-col gap-4">
	<div>
		<div class="text-base font-medium">礼品卡</div>
		<div class="text-xs text-gray-500">给指定用户或当前全体用户发放待领取兑换码。</div>
	</div>

	<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
		<div class="grid gap-2 md:grid-cols-4">
			<label class="flex items-end gap-2 pb-1">
				<input type="checkbox" bind:checked={form.all_users} />
				<span>发放给全体用户</span>
			</label>
			<label class="flex flex-col gap-1 md:col-span-3">
				<span class="text-xs text-gray-500">指定用户 ID</span>
				<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 disabled:text-gray-400 dark:border-gray-850" placeholder="多个用户用逗号、空格或换行分隔" disabled={form.all_users} bind:value={form.user_ids_text} />
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">订阅档位</span>
				<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.tier}>
					<option value="">不变更订阅</option>
					<option value="free">Free</option>
					<option value="plus">Plus</option>
					<option value="chatpower">ChatPower</option>
				</select>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">订阅天数</span>
				<input type="number" min="0" class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.duration_days} />
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">周期 Chatpoint</span>
				<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.plan_chatpoint} />
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">充值 Chatpoint</span>
				<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.check_chatpoint} />
			</label>
			<label class="flex flex-col gap-1 md:col-span-4">
				<span class="text-xs text-gray-500">备注</span>
				<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.memo} />
			</label>
		</div>
		<div class="mt-3 flex justify-end">
			<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" disabled={creating} on:click={create}>
				{creating ? '发放中' : '发放礼品卡'}
			</button>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">暂无礼品卡。</div>
	{:else}
		<div class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850">
			{#each rows as row}
				<div class="grid gap-2 p-3 text-xs md:grid-cols-[1fr_7rem_8rem_7rem_8rem_auto]">
					<div class="min-w-0">
						<div class="truncate font-medium">{userLabel(row)}</div>
						<div class="truncate text-gray-500">批次：{row.grant?.batch_id}</div>
					</div>
					<div>{statusLabel(row.grant?.status)}</div>
					<div>{tierLabel(row.code?.tier)}，{row.code?.duration_days ?? 0} 天</div>
					<div>{formatChatpoint((row.code?.plan_chatpoint_micros ?? 0) + (row.code?.check_chatpoint_micros ?? 0))} CP</div>
					<div>{formatDate(row.grant?.created_at)}</div>
					<div class="text-right">
						{#if row.grant?.status === 'pending'}
							<button type="button" class="rounded-full px-3 py-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30" on:click={() => revoke(row.grant.id)}>
								撤销
							</button>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
