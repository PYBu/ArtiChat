<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Modal from '$lib/components/common/Modal.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import {
		clearAdminRedemptionCodes,
		createAdminRedemptionCodes,
		deleteAdminRedemptionCode,
		getAdminRedemptionCodes,
		type RedemptionCode
	} from '$lib/apis/subscriptions';

	type BenefitType = 'subscription' | 'recharge' | 'legacy';

	let availableCodes: RedemptionCode[] = [];
	let archiveCodes: RedemptionCode[] = [];
	let generatedCodes: string[] = [];
	let loading = true;
	let creating = false;
	let clearing = false;
	let archiveOpen = false;
	let benefitTab: BenefitType = 'subscription';
	let archiveTab: 'disabled' | 'used' | 'expired' | 'purged' = 'disabled';

	let form = {
		benefit_type: 'subscription' as BenefitType,
		code_prefix: 'ARTI',
		mode: 'single_use',
		quantity: 1,
		max_uses: 1,
		tier: 'plus',
		duration_days: 30,
		plan_chatpoint: 100,
		check_chatpoint: 500,
		memo: ''
	};

	const formatChatpoint = (micros?: number | null) => ((micros ?? 0) / 1_000_000).toLocaleString();
	const formatDate = (value?: number | null) =>
		value ? new Date(value * 1000).toLocaleString() : '永不过期';
	const benefitLabel = (type?: string | null) => {
		if (type === 'subscription') return '订阅卡';
		if (type === 'recharge') return '额度充值卡';
		return '历史混合权益';
	};
	const tierLabel = (tier?: string | null) => {
		if (!tier) return '不变更订阅';
		if (tier === 'free') return 'Free';
		if (tier === 'plus') return 'Plus';
		if (tier === 'chatpower') return 'ChatPower';
		return tier;
	};
	const isExpired = (code: RedemptionCode) =>
		!!code.expires_at && code.expires_at <= Math.floor(Date.now() / 1000);
	const archiveMatches = (code: RedemptionCode) => {
		if (archiveTab === 'purged') return code.purged_at != null;
		if (archiveTab === 'used') return code.used_count >= code.max_uses;
		if (archiveTab === 'expired') return isExpired(code);
		return code.purged_at == null && !isExpired(code) && code.used_count < code.max_uses;
	};

	$: form.benefit_type = benefitTab;
	$: visibleCodes = availableCodes.filter((code) => code.benefit_type === benefitTab);
	$: visibleArchiveCodes = archiveCodes.filter(archiveMatches);
	$: archiveCounts = {
		disabled: archiveCodes.filter(
			(code) => code.purged_at == null && !isExpired(code) && code.used_count < code.max_uses
		).length,
		used: archiveCodes.filter((code) => code.used_count >= code.max_uses).length,
		expired: archiveCodes.filter((code) => isExpired(code)).length,
		purged: archiveCodes.filter((code) => code.purged_at != null).length
	};

	const load = async () => {
		loading = true;
		const [available, archived] = await Promise.all([
			getAdminRedemptionCodes(localStorage.token, 'available'),
			getAdminRedemptionCodes(localStorage.token, 'archive')
		]).catch((error) => {
			toast.error(`${error}`);
			return [{ items: [] }, { items: [] }];
		});
		availableCodes = available?.items ?? [];
		archiveCodes = archived?.items ?? [];
		loading = false;
	};

	const createCodes = async () => {
		creating = true;
		generatedCodes = [];
		const isSubscription = form.benefit_type === 'subscription';
		const isRecharge = form.benefit_type === 'recharge';
		const payload = {
			benefit_type: form.benefit_type,
			code_prefix: form.code_prefix.trim() || null,
			code: null,
			code_template: null,
			mode: form.mode,
			quantity: form.mode === 'multi_use' ? 1 : Number(form.quantity),
			max_uses: Number(form.max_uses),
			tier: isSubscription ? form.tier || null : null,
			duration_days: isSubscription ? Number(form.duration_days) : null,
			plan_chatpoint: isSubscription ? form.plan_chatpoint : 0,
			check_chatpoint: isRecharge ? form.check_chatpoint : 0,
			memo: form.memo || null
		};

		const created = await createAdminRedemptionCodes(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (created) {
			generatedCodes = created.raw_codes ?? [];
			toast.success('兑换码已创建。');
			await load();
		}
		creating = false;
	};

	const archiveCode = async (codeId: string) => {
		if (!window.confirm('停用后兑换码会进入归档，仍保留审计记录。继续吗？')) return;
		const archived = await deleteAdminRedemptionCode(localStorage.token, codeId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (archived) {
			toast.success('兑换码已停用并移入归档。');
			await load();
		}
	};

	const clearArchive = async () => {
		const ids = visibleArchiveCodes.filter((code) => code.purged_at == null).map((code) => code.id);
		if (!ids.length) return;
		if (!window.confirm(`将清除当前归档中的 ${ids.length} 个兑换码明文，操作不可恢复。继续吗？`))
			return;
		clearing = true;
		const cleared = await clearAdminRedemptionCodes(localStorage.token, ids).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (cleared) {
			toast.success('归档兑换码已清除。');
			await load();
		}
		clearing = false;
	};

	const copyCode = async (code: RedemptionCode) => {
		if (!code.code) return;
		await navigator.clipboard.writeText(code.code).catch(() => null);
		toast.success('兑换码已复制。');
	};

	onMount(load);
</script>

<div class="admin-operations flex flex-col gap-4">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div>
			<div class="text-base font-medium">兑换码</div>
			<div class="text-xs text-gray-500">创建订阅卡或额度充值卡；停用后进入归档。</div>
		</div>
		<button
			type="button"
			class="rounded-lg border border-gray-200/70 px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 dark:border-white/[0.08] dark:text-gray-200 dark:hover:bg-white/[0.05]"
			on:click={() => (archiveOpen = true)}
		>
			已停用与已使用
		</button>
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
					class="rounded-md px-3 py-1.5 text-xs text-gray-600 transition dark:text-gray-300"
					on:click={() => (benefitTab = value as BenefitType)}
				>
					{label}
				</button>
			{/each}
		</div>

		<div class="grid gap-3 md:grid-cols-4">
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">使用模式</span>
				<select
					class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
					bind:value={form.mode}
				>
					<option value="single_use">单次使用</option>
					<option value="multi_use">多次使用</option>
				</select>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">自定义前缀</span>
				<input
					class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs uppercase text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
					placeholder="ARTI"
					bind:value={form.code_prefix}
				/>
				<span class="text-[10px] text-gray-400">后缀由服务端安全随机生成</span>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">生成数量</span>
				<input
					type="number"
					min="1"
					class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 disabled:text-gray-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
					disabled={form.mode === 'multi_use'}
					bind:value={form.quantity}
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">最大使用次数</span>
				<input
					type="number"
					min="1"
					class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
					bind:value={form.max_uses}
				/>
			</label>

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
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">Plan Chatpoint</span>
					<input
						type="number"
						min="0"
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.plan_chatpoint}
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
				class="rounded-lg bg-black px-3 py-1.5 text-xs font-medium text-white transition hover:bg-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-gray-100"
				disabled={creating || !form.code_prefix.trim()}
				on:click={createCodes}
			>
				{creating ? '创建中...' : '创建兑换码'}
			</button>
		</div>
	</div>

	{#if generatedCodes.length > 0}
		<div
			class="rounded-lg border border-green-200/70 bg-green-50/30 p-3 text-xs dark:border-green-900/60 dark:bg-green-950/20"
		>
			<div class="mb-2 font-medium">本次生成的兑换码</div>
			<div class="grid gap-1 font-mono">
				{#each generatedCodes as code}
					<div>{code}</div>
				{/each}
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if availableCodes.length === 0}
		<div
			class="rounded-lg border border-gray-100/60 bg-gray-50/30 p-3 text-xs text-gray-500 dark:border-white/[0.06] dark:bg-white/[0.02]"
		>
			暂无可用兑换码。
		</div>
	{:else}
		<div class="flex flex-wrap gap-1 rounded-lg bg-gray-50/70 p-1 dark:bg-white/[0.04]">
			{#each [['subscription', '订阅卡'], ['recharge', '额度充值卡'], ['legacy', '历史混合权益']] as [value, label]}
				<button
					type="button"
					class:font-medium={benefitTab === value}
					class:bg-white={benefitTab === value}
					class:shadow-sm={benefitTab === value}
					class="rounded-md px-3 py-1.5 text-xs text-gray-600 transition dark:text-gray-300"
					on:click={() => (benefitTab = value as BenefitType)}
				>
					{label}
				</button>
			{/each}
		</div>
		{#if visibleCodes.length === 0}
			<div
				class="rounded-lg border border-gray-100/60 bg-gray-50/30 p-3 text-xs text-gray-500 dark:border-white/[0.06] dark:bg-white/[0.02]"
			>
				当前分类暂无可用兑换码。
			</div>
		{:else}
			<div class="grid gap-2">
				{#each visibleCodes as code (code.id)}
					<div
						class="rounded-lg border border-gray-100/60 bg-white/40 p-3 text-xs dark:border-white/[0.06] dark:bg-white/[0.02]"
					>
						<div class="flex flex-wrap items-start justify-between gap-3">
							<div class="min-w-0">
								<div class="font-mono font-medium">{code.code ?? code.code_preview}</div>
								<div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-gray-500">
									<span
										class:text-green-600={code.benefit_type === 'recharge'}
										class:text-blue-600={code.benefit_type !== 'recharge'}
										>{benefitLabel(code.benefit_type)}</span
									>
									{#if code.benefit_type === 'subscription'}<span
											>{tierLabel(code.tier)} · {code.duration_days ?? 0} 天</span
										>{/if}
									{#if code.benefit_type === 'recharge'}<span
											>{formatChatpoint(code.check_chatpoint_micros)} CP</span
										>{/if}
									<span>{code.used_count} / {code.max_uses} 次</span>
									<span>{formatDate(code.expires_at)}</span>
								</div>
							</div>
							<div class="flex shrink-0 gap-2">
								<button
									type="button"
									class="rounded-lg border border-gray-200/70 px-2.5 py-1.5 text-xs text-gray-600 hover:bg-gray-50 dark:border-white/[0.08] dark:text-gray-300 dark:hover:bg-white/[0.05]"
									on:click={() => copyCode(code)}
								>
									复制
								</button>
								<button
									type="button"
									class="rounded-lg border border-red-200/70 px-2.5 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 dark:border-red-900/60 dark:text-red-300 dark:hover:bg-red-950/30"
									on:click={() => archiveCode(code.id)}
								>
									停用
								</button>
							</div>
						</div>
						{#if code.memo}<div class="mt-2 text-gray-500">{code.memo}</div>{/if}
					</div>
				{/each}
			</div>
		{/if}
	{/if}
</div>

<Modal
	bind:show={archiveOpen}
	size="lg"
	closeOnBackdrop={false}
	closeOnEscape={false}
	className="rounded-lg bg-white dark:bg-gray-900"
>
	<div class="flex max-h-[80vh] flex-col">
		<div
			class="flex items-start justify-between border-b border-gray-100/70 p-4 dark:border-white/[0.06]"
		>
			<div>
				<div class="text-sm font-medium">兑换码归档</div>
				<div class="mt-1 text-[11px] text-gray-500">
					停用、已使用、已过期和已清除的兑换码保留在这里。
				</div>
			</div>
			<button
				type="button"
				class="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-white/[0.06]"
				aria-label="关闭"
				on:click={() => (archiveOpen = false)}
			>
				<XMark className="size-4" strokeWidth="2" />
			</button>
		</div>
		<div class="min-h-0 overflow-y-auto p-4">
			<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
				<div class="flex flex-wrap gap-1 rounded-lg bg-gray-50/70 p-1 dark:bg-white/[0.04]">
					{#each [['disabled', `已停用 ${archiveCounts.disabled}`], ['used', `已使用 ${archiveCounts.used}`], ['expired', `已过期 ${archiveCounts.expired}`], ['purged', `已清除 ${archiveCounts.purged}`]] as [value, label]}
						<button
							type="button"
							class:font-medium={archiveTab === value}
							class:bg-white={archiveTab === value}
							class:shadow-sm={archiveTab === value}
							class="rounded-md px-2.5 py-1.5 text-xs text-gray-600 dark:text-gray-300"
							on:click={() => (archiveTab = value as typeof archiveTab)}>{label}</button
						>
					{/each}
				</div>
				<button
					type="button"
					class="rounded-lg border border-red-200/70 px-2.5 py-1.5 text-xs font-medium text-red-600 disabled:cursor-not-allowed disabled:opacity-40 dark:border-red-900/60 dark:text-red-300"
					disabled={clearing || !visibleArchiveCodes.some((code) => code.purged_at == null)}
					on:click={clearArchive}>清除当前列表</button
				>
			</div>
			{#if visibleArchiveCodes.length === 0}
				<div
					class="rounded-lg border border-gray-100/60 bg-gray-50/30 p-3 text-xs text-gray-500 dark:border-white/[0.06] dark:bg-white/[0.02]"
				>
					当前归档没有记录。
				</div>
			{:else}
				<div class="grid gap-2">
					{#each visibleArchiveCodes as code (code.id)}
						<div
							class="rounded-lg border border-gray-100/60 bg-white/40 p-3 text-xs dark:border-white/[0.06] dark:bg-white/[0.02]"
						>
							<div class="flex flex-wrap items-start justify-between gap-2">
								<div class="min-w-0">
									<div class="font-mono font-medium">{code.code ?? code.code_preview}</div>
									<div class="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-gray-500">
										<span>{benefitLabel(code.benefit_type)}</span><span
											>{code.used_count} / {code.max_uses} 次</span
										><span>更新于 {formatDate(code.updated_at)}</span>
									</div>
								</div>
								{#if code.purged_at}<span class="text-gray-400">明文已清除</span>{/if}
							</div>
							{#if code.memo}<div class="mt-2 text-gray-500">{code.memo}</div>{/if}
						</div>
					{/each}
				</div>
			{/if}
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
