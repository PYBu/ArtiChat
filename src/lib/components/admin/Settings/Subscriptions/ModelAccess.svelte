<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		getAdminSubscriptionModels,
		updateAdminModelSubscriptionPolicy
	} from '$lib/apis/subscriptions';

	const tiers = [
		{ id: 'free', label: '免费版' },
		{ id: 'plus', label: 'Plus' },
		{ id: 'chatpower', label: 'ChatPower' }
	];

	let rows: any[] = [];
	let loading = true;

	const defaultPolicy = () => ({
		allowed_tiers: ['free', 'plus', 'chatpower'],
		quota_mode: 'metered',
		usage_multiplier: '1'
	});

	const normalize = (model: any) => ({
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
		loading = false;
	};

	const toggleTier = (row: any, tier: string) => {
		const allowed = new Set(row.subscription.allowed_tiers ?? []);
		if (allowed.has(tier)) {
			allowed.delete(tier);
		} else {
			allowed.add(tier);
		}
		row.subscription.allowed_tiers = tiers.map((item) => item.id).filter((item) => allowed.has(item));
	};

	const save = async (row: any) => {
		const updated = await updateAdminModelSubscriptionPolicy(localStorage.token, row.id, row.subscription).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);
		if (updated) toast.success('模型订阅策略已保存。');
	};

	onMount(load);
</script>

<div class="flex flex-col gap-3">
	<div>
		<div class="text-base font-medium">模型权限</div>
		<div class="text-xs text-gray-500">控制模型可见范围、扣费模式和 Chatpoint 扣费倍率。</div>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">暂无模型。</div>
	{:else}
		<div class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850">
			{#each rows as row (row.id)}
				<div class="grid gap-3 p-3 lg:grid-cols-[1fr_15rem_11rem_8rem_auto]">
					<div class="min-w-0">
						<div class="truncate font-medium">{row.name ?? row.id}</div>
						<div class="truncate text-xs text-gray-500">{row.id}</div>
					</div>

					<div class="flex flex-wrap items-center gap-2">
						{#each tiers as tier}
							<label class="flex items-center gap-1 rounded-full bg-gray-50 px-2 py-1 text-xs dark:bg-gray-900">
								<input
									type="checkbox"
									checked={(row.subscription.allowed_tiers ?? []).includes(tier.id)}
									on:change={() => toggleTier(row, tier.id)}
								/>
								<span>{tier.label}</span>
							</label>
						{/each}
					</div>

					<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.subscription.quota_mode}>
						<option value="metered">按量扣费</option>
						<option value="unlimited">无限使用</option>
					</select>

					<input
						class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 disabled:text-gray-400 dark:border-gray-850"
						disabled={row.subscription.quota_mode === 'unlimited'}
						bind:value={row.subscription.usage_multiplier}
					/>

					<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" on:click={() => save(row)}>
						保存
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
