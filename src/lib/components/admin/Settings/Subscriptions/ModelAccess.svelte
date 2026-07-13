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

<div class="flex flex-col gap-3">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div>
			<div class="text-base font-medium">模型权限</div>
			<div class="text-xs text-gray-500">
				控制模型可见范围、扣费模式和每百万 Token 的 Chatpoint 价格。
			</div>
		</div>
		<button
			type="button"
			class="rounded-lg bg-black px-3 py-1.5 text-white disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black"
			disabled={!dirty || saving}
			on:click={save}
		>
			{saving ? '保存中...' : '保存更改'}
		</button>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">
			暂无模型。
		</div>
	{:else}
		<div
			class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850"
		>
			{#each rows as row (row.id)}
				<div class="grid gap-3 p-3 lg:grid-cols-[1fr_15rem_11rem]">
					<div class="min-w-0">
						<div class="truncate font-medium">{row.name ?? row.id}</div>
						<div class="truncate text-xs text-gray-500">{row.id}</div>
					</div>

					<div class="flex flex-wrap items-center gap-2">
						{#each tiers as tier}
							<label
								class="flex items-center gap-1 rounded-full bg-gray-50 px-2 py-1 text-xs dark:bg-gray-900"
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
						class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
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
									class="min-w-0 rounded-lg border border-gray-100 bg-transparent px-2 py-1 disabled:text-gray-400 dark:border-gray-850"
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
