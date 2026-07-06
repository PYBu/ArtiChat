<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getAdminSubscriptionPlans, updateAdminSubscriptionPlan } from '$lib/apis/subscriptions';

	let rows: any[] = [];
	let loading = true;

	const formatChatpoint = (micros?: number | null) => `${(micros ?? 0) / 1_000_000}`;

	const normalizePlan = (plan: any) => ({
		...plan,
		plan_chatpoint: formatChatpoint(plan.plan_chatpoint_allowance_micros),
		featuresText: JSON.stringify(plan.features ?? {}, null, 2)
	});

	const load = async () => {
		loading = true;
		rows = await getAdminSubscriptionPlans(localStorage.token)
			.then((plans) => (plans ?? []).map(normalizePlan))
			.catch((error) => {
				toast.error(`${error}`);
				return [];
			});
		loading = false;
	};

	const save = async (row: any) => {
		let features = {};
		try {
			features = row.featuresText?.trim() ? JSON.parse(row.featuresText) : {};
		} catch (error) {
			toast.error('功能配置必须是有效的 JSON。');
			return;
		}

		const updated = await updateAdminSubscriptionPlan(localStorage.token, row.id, {
			display_name: row.display_name,
			plan_chatpoint: row.plan_chatpoint,
			period_days: Number(row.period_days),
			features,
			is_active: !!row.is_active
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (updated) {
			row = Object.assign(row, normalizePlan(updated));
			toast.success('订阅计划已保存。');
		}
	};

	onMount(load);
</script>

<div class="flex flex-col gap-3">
	<div>
		<div class="text-base font-medium">订阅计划</div>
		<div class="text-xs text-gray-500">计划变更会应用于之后的新订阅和周期重置。</div>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">暂无订阅计划。</div>
	{:else}
		<div class="flex flex-col gap-2">
			{#each rows as row (row.id)}
				<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
					<div class="grid gap-2 md:grid-cols-5">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">名称</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.display_name} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">档位</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" value={row.id} disabled />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">周期 Chatpoint</span>
							<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.plan_chatpoint} />
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">周期天数</span>
							<input type="number" min="1" class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={row.period_days} />
						</label>
						<label class="flex items-end gap-2 pb-1">
							<input type="checkbox" bind:checked={row.is_active} />
							<span>启用</span>
						</label>
					</div>
					<label class="mt-2 flex flex-col gap-1">
						<span class="text-xs text-gray-500">功能配置 JSON</span>
						<textarea class="min-h-20 rounded-lg border border-gray-100 bg-transparent px-2 py-1 font-mono text-xs dark:border-gray-850" bind:value={row.featuresText}></textarea>
					</label>
					<div class="mt-3 flex justify-end">
						<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" on:click={() => save(row)}>
							保存
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
