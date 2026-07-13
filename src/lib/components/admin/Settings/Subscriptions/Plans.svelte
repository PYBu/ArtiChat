<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		getAdminSubscriptionPlans,
		updateAdminSubscriptionPlan,
		type SubscriptionPlan
	} from '$lib/apis/subscriptions';

	type EditablePlan = SubscriptionPlan & {
		plan_chatpoint: string;
		icon: string;
		subtitle: string;
		highlightsText: string;
		model_summary: string;
		cta_label: string;
	};

	let rows: EditablePlan[] = [];
	let loading = true;

	const formatChatpoint = (micros?: number | null) => `${(micros ?? 0) / 1_000_000}`;

	const normalizePlan = (plan: SubscriptionPlan): EditablePlan => {
		const features = !Array.isArray(plan.features) && plan.features ? plan.features : {};
		return {
			...plan,
			plan_chatpoint: formatChatpoint(plan.plan_chatpoint_allowance_micros),
			icon: features.icon ?? '',
			subtitle: features.subtitle ?? '',
			highlightsText: (features.highlights ?? []).join('\n'),
			model_summary: features.model_summary ?? '',
			cta_label: features.cta_label ?? ''
		};
	};

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

	const save = async (row: EditablePlan) => {
		const features = {
			icon: row.icon || undefined,
			subtitle: row.subtitle || undefined,
			highlights: (row.highlightsText ?? '')
				.split('\n')
				.map((item) => item.trim())
				.filter(Boolean),
			model_summary: row.model_summary || undefined,
			cta_label: row.cta_label || undefined
		};

		const updated = await updateAdminSubscriptionPlan(localStorage.token, row.id, {
			display_name: row.display_name,
			description: row.description,
			plan_chatpoint: row.plan_chatpoint,
			period_days: Number(row.period_days),
			features,
			is_active: !!row.is_active
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (updated) {
			Object.assign(row, normalizePlan(updated));
			toast.success('订阅计划已保存。');
		}
	};

	onMount(load);
</script>

<div class="flex flex-col gap-3">
	<div>
		<div class="text-base font-medium">订阅计划</div>
		<div class="text-xs text-gray-500">
			计划变更会应用于之后的新订阅和周期重置，不影响已订阅用户的快照额度。
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">
			暂无订阅计划。
		</div>
	{:else}
		<div class="flex flex-col gap-2">
			{#each rows as row (row.id)}
				<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
					<div class="grid gap-2 md:grid-cols-5">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">名称</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.display_name}
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">档位</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								value={row.id}
								disabled
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">周期 Chatpoint</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.plan_chatpoint}
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">周期天数</span>
							<input
								type="number"
								min="1"
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.period_days}
							/>
						</label>
						<label class="flex items-end gap-2 pb-1">
							<input type="checkbox" bind:checked={row.is_active} />
							<span>启用</span>
						</label>
					</div>

					<div class="mt-3 grid gap-2 md:grid-cols-2">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">订阅介绍</span>
							<textarea
								class="min-h-20 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.description}
							></textarea>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">可访问模型说明</span>
							<textarea
								class="min-h-20 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.model_summary}
							></textarea>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">Icon</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								placeholder="sparkles / badge / zap"
								bind:value={row.icon}
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">副标题</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.subtitle}
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">按钮文案</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.cta_label}
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">功能点，每行一条</span>
							<textarea
								class="min-h-20 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.highlightsText}
							></textarea>
						</label>
					</div>

					<div class="mt-3 flex justify-end">
						<button
							type="button"
							class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black"
							on:click={() => save(row)}
						>
							保存
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
