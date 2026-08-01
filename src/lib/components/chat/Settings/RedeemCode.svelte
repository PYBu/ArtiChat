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
	import { notifySubscriptionChanged } from '$lib/stores/subscriptions';
	import Gift from '$lib/components/icons/Gift.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';

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
		} catch (err) {
			error = `${err}`;
			toast.error(error);
		}
		loading = false;
	};

	onMount(loadGiftCards);
</script>

<div id="tab-redeem-code" class="flex h-full min-h-0 flex-col overflow-y-auto pr-1 text-sm">
	<div class="mx-auto flex w-full max-w-2xl flex-col gap-3">
		<header class="border-b border-gray-100 pb-3 dark:border-gray-850">
			<h2 class="text-sm font-medium text-gray-900 dark:text-white">兑换码</h2>
			<p class="mt-1 text-[0.6875rem] text-gray-500 dark:text-gray-400">
				兑换权益或领取管理员发放的礼品。
			</p>
		</header>

		<section class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
			<div class="flex items-start gap-3">
				<div
					class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gray-50 text-gray-700 dark:bg-gray-900 dark:text-gray-200"
				>
					<Sparkles className="size-3.5" />
				</div>
				<div class="min-w-0">
					<div class="text-[13px] font-medium">兑换权益</div>
					<div class="mt-1 text-[0.6875rem] text-gray-500 dark:text-gray-400">
						输入订阅卡或额度充值卡兑换码。
					</div>
				</div>
			</div>
			<div class="mt-3 flex flex-col gap-2 sm:flex-row">
				<input
					class="h-7 min-w-0 flex-1 rounded-lg border border-gray-200 bg-transparent px-2.5 text-xs outline-hidden transition focus:border-gray-400 dark:border-gray-800 dark:focus:border-gray-600"
					placeholder="输入兑换码"
					aria-label="输入兑换码"
					bind:value={code}
				/>
				<button
					class="h-7 w-full shrink-0 rounded-lg bg-black px-3 text-xs font-medium text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto dark:bg-white dark:text-black dark:hover:bg-gray-200"
					type="button"
					disabled={loading || !code.trim()}
					on:click={redeem}
				>
					{loading ? '处理中' : '兑换'}
				</button>
			</div>
		</section>

		{#if !giftLoading && giftCards.length > 0}
			{#each giftCards as gift}
				<section class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
					<div class="flex items-start gap-3">
						<div
							class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gray-50 text-gray-700 dark:bg-gray-900 dark:text-gray-200"
						>
							<Gift className="size-3.5" />
						</div>
						<div class="min-w-0">
							<div class="truncate text-[13px] font-medium">{gift.memo ?? '礼品卡'}</div>
							<div class="mt-1 text-[0.6875rem] text-gray-500 dark:text-gray-400">
								管理员发放的待领取礼品，领取后会自动应用权益。
							</div>
						</div>
					</div>
					<div
						class="mt-3 flex flex-col items-stretch gap-2 text-[0.6875rem] text-gray-500 dark:text-gray-400 sm:flex-row sm:items-center sm:justify-between"
					>
						<span>批次：{gift.batch_id}</span>
						<button
							class="inline-flex h-7 w-full shrink-0 items-center justify-center gap-1.5 rounded-lg bg-black px-3 text-xs font-medium text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto dark:bg-white dark:text-black dark:hover:bg-gray-200"
							type="button"
							disabled={loading}
							on:click={() => claim(gift.id)}
						>
							<Gift className="size-3.5" />
							领取礼品
						</button>
					</div>
				</section>
			{/each}
		{/if}

		{#if error}
			<div class="rounded-lg border border-red-200 p-3 text-xs text-red-600 dark:border-red-900">
				{error}
			</div>
		{/if}

		{#if result}
			<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
				<div class="text-[13px] font-medium">{result.tier_after ?? result.subscription?.tier}</div>
				<div class="mt-2 grid grid-cols-2 gap-2 text-[0.6875rem] text-gray-600 dark:text-gray-300">
					<div>周期 Chatpoint</div>
					<div class="text-right">{formatChatpoint(result.plan_delta_micros)}</div>
					<div>充值 Chatpoint</div>
					<div class="text-right">{formatChatpoint(result.check_delta_micros)}</div>
				</div>
			</div>
		{/if}
	</div>
</div>
