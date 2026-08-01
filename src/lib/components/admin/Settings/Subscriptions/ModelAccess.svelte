<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		getAdminSubscriptionModels,
		updateAdminModelSubscriptionPolicies,
		type AdminSubscriptionModel,
		type SubscriptionModelPolicy
	} from '$lib/apis/subscriptions';

	const tiers = [
		{ id: 'free', label: 'Free' },
		{ id: 'plus', label: 'Plus' },
		{ id: 'chatpower', label: 'ChatPower' }
	];

	type PriceField =
		| 'input_chatpoint_per_million'
		| 'output_chatpoint_per_million'
		| 'cache_creation_chatpoint_per_million'
		| 'cache_read_chatpoint_per_million';
	type EditableSubscriptionModel = Omit<AdminSubscriptionModel, 'subscription'> & {
		subscription: SubscriptionModelPolicy;
	};

	let rows: EditableSubscriptionModel[] = [];
	let loading = true;
	let saving = false;
	let dirty = false;
	let searchQuery = '';
	let providerFilter = '';
	let modeFilter = '';

	const defaultPolicy = (): SubscriptionModelPolicy => ({
		allowed_tiers: ['free', 'plus', 'chatpower'],
		quota_mode: 'metered',
		usage_multiplier: '1',
		input_chatpoint_per_million: '100',
		output_chatpoint_per_million: '100',
		cache_creation_chatpoint_per_million: '0',
		cache_read_chatpoint_per_million: '0'
	});

	const priceFields: Array<{ key: PriceField; label: string }> = [
		{ key: 'input_chatpoint_per_million', label: '输入' },
		{ key: 'output_chatpoint_per_million', label: '输出' },
		{ key: 'cache_creation_chatpoint_per_million', label: '创建缓存' },
		{ key: 'cache_read_chatpoint_per_million', label: '读取缓存' }
	];

	const normalize = (model: AdminSubscriptionModel): EditableSubscriptionModel => ({
		...model,
		subscription: { ...defaultPolicy(), ...(model.subscription ?? {}) }
	});

	const providerLabel = (row: EditableSubscriptionModel) => row.provider || '未标注';

	$: providers = Array.from(new Set(rows.map(providerLabel))).sort((a, b) => a.localeCompare(b));
	$: filteredRows = rows.filter((row) => {
		const query = searchQuery.trim().toLocaleLowerCase();
		const matchesQuery =
			!query ||
			[row.name, row.id, row.base_model_id, providerLabel(row)]
				.filter(Boolean)
				.some((value) => value!.toLocaleLowerCase().includes(query));
		const matchesProvider = !providerFilter || providerLabel(row) === providerFilter;
		const matchesMode = !modeFilter || row.subscription.quota_mode === modeFilter;
		return matchesQuery && matchesProvider && matchesMode;
	});

	const load = async () => {
		loading = true;
		rows = await getAdminSubscriptionModels(localStorage.token)
			.then((models) => (models ?? []).map(normalize))
			.catch((error) => {
				toast.error(`${error}`);
				return [];
			});
		dirty = false;
		loading = false;
	};

	const markDirty = () => {
		dirty = true;
		rows = [...rows];
	};

	const toggleTier = (row: EditableSubscriptionModel, tier: string) => {
		const allowed = new Set(row.subscription.allowed_tiers ?? []);
		if (allowed.has(tier)) {
			allowed.delete(tier);
		} else {
			allowed.add(tier);
		}
		row.subscription.allowed_tiers = tiers
			.map((item) => item.id)
			.filter((item) => allowed.has(item));
		markDirty();
	};

	const save = async () => {
		if (!dirty || saving) return;
		saving = true;
		const updated = await updateAdminModelSubscriptionPolicies(
			localStorage.token,
			rows.map((row) => ({ id: row.id, subscription: row.subscription }))
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (updated) {
			rows = updated.map(normalize);
			dirty = false;
			toast.success('模型权限已保存。');
		}
		saving = false;
	};

	onMount(load);
</script>

<div class="admin-operations flex flex-col gap-4">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div>
			<div class="text-base font-medium">模型权限</div>
			<div class="text-xs text-gray-500">
				控制模型可见范围、扣费模式和每百万 Token 的 Chatpoint 价格。
			</div>
		</div>
		<button
			type="button"
			class="rounded-lg bg-black px-3 py-1.5 text-xs font-medium text-white transition hover:bg-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black dark:hover:bg-gray-100"
			disabled={!dirty || saving}
			on:click={save}
		>
			{saving ? '保存中...' : '保存更改'}
		</button>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div
			class="rounded-lg border border-gray-100/60 bg-gray-50/30 p-3 text-xs text-gray-500 dark:border-white/[0.06] dark:bg-white/[0.02]"
		>
			暂无模型。
		</div>
	{:else}
		<div class="flex flex-wrap items-center gap-2">
			<input
				class="h-7 min-w-52 flex-1 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500"
				placeholder="搜索模型"
				aria-label="搜索模型"
				bind:value={searchQuery}
			/>
			<select
				class="h-7 w-36 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500"
				aria-label="筛选提供商"
				bind:value={providerFilter}
			>
				<option value="">全部提供商</option>
				{#each providers as provider}
					<option value={provider}>{provider}</option>
				{/each}
			</select>
			<select
				class="h-7 w-32 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500"
				aria-label="筛选模式"
				bind:value={modeFilter}
			>
				<option value="">全部模式</option>
				<option value="metered">按量扣费</option>
				<option value="unlimited">无限使用</option>
			</select>
		</div>
		{#if filteredRows.length === 0}
			<div
				class="rounded-lg border border-gray-100/60 bg-gray-50/30 p-3 text-xs text-gray-500 dark:border-white/[0.06] dark:bg-white/[0.02]"
			>
				没有符合筛选条件的模型。
			</div>
		{/if}
		<div class="flex flex-col gap-2">
			{#each filteredRows as row (row.id)}
				<div
					class="grid gap-3 rounded-lg border border-gray-100/60 bg-white/40 p-3 dark:border-white/[0.06] dark:bg-white/[0.02] lg:grid-cols-[1fr_15rem_11rem]"
				>
					<div class="min-w-0">
						<div class="truncate font-medium">{row.name ?? row.id}</div>
						<div class="truncate text-xs text-gray-500">{row.id}</div>
					</div>

					<div class="flex flex-wrap items-center gap-2">
						{#each tiers as tier}
							<label
								class="flex items-center gap-1 rounded-lg border border-gray-100/60 bg-gray-50/50 px-2 py-1 text-xs dark:border-white/[0.06] dark:bg-white/[0.03]"
							>
								<input
									type="checkbox"
									checked={(row.subscription.allowed_tiers ?? []).includes(tier.id)}
									on:change={() => toggleTier(row, tier.id)}
								/>
								<span>{tier.label}</span>
							</label>
						{/each}
					</div>

					<select
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500"
						bind:value={row.subscription.quota_mode}
						on:change={markDirty}
					>
						<option value="metered">按量扣费</option>
						<option value="unlimited">无限使用</option>
					</select>

					<div class="grid grid-cols-2 gap-2 lg:col-span-3 lg:grid-cols-4">
						{#each priceFields as field}
							<label class="flex min-w-0 flex-col gap-1">
								<span class="text-xs text-gray-500">{field.label}</span>
								<input
									type="number"
									min="0"
									step="any"
									class="h-7 min-w-0 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors focus:border-blue-400 disabled:text-gray-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500"
									disabled={row.subscription.quota_mode === 'unlimited'}
									bind:value={row.subscription[field.key]}
									on:input={markDirty}
								/>
								<span class="text-[10px] text-gray-400">Chatpoint / 1M Token</span>
							</label>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

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
