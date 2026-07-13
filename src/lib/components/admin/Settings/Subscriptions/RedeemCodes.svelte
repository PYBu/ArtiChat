<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		createAdminRedemptionCodes,
		deleteAdminRedemptionCode,
		getAdminRedemptionCodes,
		type RedemptionCode
	} from '$lib/apis/subscriptions';

	let codes: RedemptionCode[] = [];
	let generatedCodes: string[] = [];
	let loading = true;
	let creating = false;

	let form = {
		code: '',
		mode: 'single_use',
		quantity: 1,
		max_uses: 1,
		tier: 'plus',
		duration_days: 30,
		plan_chatpoint: 100,
		check_chatpoint: 0,
		memo: ''
	};

	const formatChatpoint = (micros?: number | null) => ((micros ?? 0) / 1_000_000).toLocaleString();
	const formatDate = (value?: number | null) =>
		value ? new Date(value * 1000).toLocaleString() : '-';
	const modeLabel = (mode?: string) => {
		if (mode === 'single_use') return '单次使用';
		if (mode === 'multi_use') return '多次使用';
		return mode || '-';
	};
	const tierLabel = (tier?: string | null) => {
		if (!tier) return '不变更订阅';
		if (tier === 'free') return 'Free';
		if (tier === 'plus') return 'Plus';
		if (tier === 'chatpower') return 'ChatPower';
		return tier;
	};

	const load = async () => {
		loading = true;
		const response = await getAdminRedemptionCodes(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return { items: [] };
		});
		codes = response?.items ?? [];
		loading = false;
	};

	const createCodes = async () => {
		creating = true;
		generatedCodes = [];
		const payload = {
			...form,
			quantity: form.mode === 'multi_use' || form.code.trim() ? 1 : Number(form.quantity),
			max_uses: Number(form.max_uses),
			duration_days: Number(form.duration_days),
			tier: form.tier || null,
			code: form.code.trim() || null,
			memo: form.memo || null
		};

		const created = await createAdminRedemptionCodes(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (created) {
			generatedCodes = created.raw_codes ?? [];
			form.code = '';
			toast.success('兑换码已创建。');
			await load();
		}
		creating = false;
	};

	const removeCode = async (codeId: string) => {
		const deleted = await deleteAdminRedemptionCode(localStorage.token, codeId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (deleted) {
			toast.success('兑换码已删除。');
			await load();
		}
	};

	onMount(load);
</script>

<div class="flex flex-col gap-4">
	<div>
		<div class="text-base font-medium">兑换码</div>
		<div class="text-xs text-gray-500">生成用于开通订阅时长和发放 Chatpoint 的兑换码。</div>
	</div>

	<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
		<div class="grid gap-2 md:grid-cols-4">
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">模式</span>
				<select
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.mode}
				>
					<option value="single_use">单次使用</option>
					<option value="multi_use">多次使用</option>
				</select>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">自定义兑换码</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					placeholder="留空自动生成"
					bind:value={form.code}
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">生成数量</span>
				<input
					type="number"
					min="1"
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 disabled:text-gray-400 dark:border-gray-850"
					disabled={form.mode === 'multi_use' || !!form.code.trim()}
					bind:value={form.quantity}
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">最大使用次数</span>
				<input
					type="number"
					min="1"
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.max_uses}
				/>
			</label>
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
			<label class="flex flex-col gap-1">
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
				class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black"
				disabled={creating}
				on:click={createCodes}
			>
				{creating ? '创建中' : '创建兑换码'}
			</button>
		</div>
	</div>

	{#if generatedCodes.length > 0}
		<div class="rounded-lg border border-green-200 p-3 text-xs dark:border-green-900">
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
	{:else if codes.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">
			暂无兑换码。
		</div>
	{:else}
		<div
			class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850"
		>
			{#each codes as code}
				<div class="grid gap-2 p-3 text-xs md:grid-cols-[1fr_7rem_7rem_8rem_7rem_auto]">
					<div>
						<div class="font-mono font-medium">{code.code ?? code.code_preview}</div>
						{#if !code.code}
							<div class="text-[11px] text-yellow-600">旧兑换码未保存完整内容</div>
						{/if}
						<div class="text-gray-500">{code.memo ?? '-'}</div>
					</div>
					<div>{modeLabel(code.mode)}</div>
					<div>{code.used_count}/{code.max_uses}</div>
					<div>{tierLabel(code.tier)}，{code.duration_days ?? 0} 天</div>
					<div>{formatChatpoint(code.plan_chatpoint_micros + code.check_chatpoint_micros)} CP</div>
					<div class="flex justify-end">
						<button
							type="button"
							class="rounded-full px-3 py-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
							on:click={() => removeCode(code.id)}
						>
							删除
						</button>
					</div>
					<div class="md:col-span-6 text-gray-500">
						过期时间：{formatDate(code.expires_at)} · 状态：{code.is_active ? '可用' : '已停用'}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
