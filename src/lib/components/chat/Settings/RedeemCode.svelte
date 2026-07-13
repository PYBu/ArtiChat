<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		claimGiftCard,
		getPendingGiftCards,
		redeemSubscriptionCode,
		type GiftCardGrant,
		type RedemptionResult
	} from '$lib/apis/subscriptions';
	import { notifySubscriptionChanged } from '$lib/stores';

	const dispatch = createEventDispatcher();
	let code = '';
	let result: RedemptionResult | null = null;
	let error = '';
	let loading = false;
	let giftCards: GiftCardGrant[] = [];
	let giftLoading = true;

	const formatChatpoint = (micros?: number | null) => {
		return ((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 6 });
	};

	const loadGiftCards = async () => {
		giftLoading = true;
		const response = await getPendingGiftCards(localStorage.token).catch(() => ({ items: [] }));
		giftCards = response?.items ?? [];
		giftLoading = false;
	};

	const redeem = async () => {
		if (!code.trim() || loading) return;
		loading = true;
		error = '';
		result = null;
		try {
			result = await redeemSubscriptionCode(localStorage.token, code.trim());
			code = '';
			toast.success('兑换成功。');
			await notifySubscriptionChanged();
			dispatch('redeemed');
		} catch (err) {
			error = `${err}`;
			toast.error(error);
		}
		loading = false;
	};

	const claim = async (grantId: string) => {
		if (loading) return;
		loading = true;
		error = '';
		result = null;
		try {
			result = await claimGiftCard(localStorage.token, grantId);
			toast.success('礼品卡已领取。');
			await notifySubscriptionChanged();
			await loadGiftCards();
			dispatch('redeemed');
		} catch (err) {
			error = `${err}`;
			toast.error(error);
		}
		loading = false;
	};

	onMount(loadGiftCards);
</script>

<div id="tab-redeem-code" class="flex h-full flex-col gap-4 text-sm">
	<div class="text-base font-medium">兑换码</div>

	{#if !giftLoading && giftCards.length > 0}
		<div
			class="rounded-lg border border-green-200 bg-green-50/60 p-3 dark:border-green-900 dark:bg-green-950/20"
		>
			<div class="font-medium">你有待领取礼品卡</div>
			<div class="mt-1 text-xs text-gray-600 dark:text-gray-300">
				管理员已向你的账号发放礼品卡，领取后会自动兑换订阅或 Chatpoint。
			</div>
			<div class="mt-3 flex flex-col gap-2">
				{#each giftCards as gift}
					<div
						class="flex items-center justify-between gap-3 rounded-lg bg-white p-2 text-xs dark:bg-gray-900"
					>
						<div class="min-w-0">
							<div class="truncate font-medium">{gift.memo ?? '礼品卡'}</div>
							<div class="text-gray-500">批次：{gift.batch_id}</div>
						</div>
						<button
							class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black"
							type="button"
							on:click={() => claim(gift.id)}
						>
							领取
						</button>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<div class="flex gap-2">
		<input
			class="w-full rounded-lg border border-gray-100 bg-transparent px-3 py-2 outline-hidden dark:border-gray-850"
			placeholder="输入兑换码"
			bind:value={code}
		/>
		<button
			class="rounded-full bg-black px-4 py-2 text-white dark:bg-white dark:text-black"
			type="button"
			on:click={redeem}
		>
			{loading ? '处理中' : '兑换'}
		</button>
	</div>

	{#if error}
		<div class="rounded-lg border border-red-200 p-3 text-red-600 dark:border-red-900">{error}</div>
	{/if}

	{#if result}
		<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
			<div class="font-medium">{result.tier_after ?? result.subscription?.tier}</div>
			<div class="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-300">
				<div>周期 Chatpoint</div>
				<div class="text-right">{formatChatpoint(result.plan_delta_micros)}</div>
				<div>充值 Chatpoint</div>
				<div class="text-right">{formatChatpoint(result.check_delta_micros)}</div>
			</div>
		</div>
	{/if}
</div>
