<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Modal from '$lib/components/common/Modal.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Badge from '$lib/components/icons/UserBadgeCheck.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import CheckCircle from '$lib/components/icons/CheckCircle.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import AdminSettingField from '$lib/components/admin/Settings/AdminSettingField.svelte';
	import AdminSettingRow from '$lib/components/admin/Settings/AdminSettingRow.svelte';
	import AdminSettingSection from '$lib/components/admin/Settings/AdminSettingSection.svelte';
	import {
		getAdminSubscriptionPlans,
		updateAdminSubscriptionPlan,
		type SubscriptionFeatures,
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

	const iconMap = {
		badge: Badge,
		sparkles: Sparkles,
		zap: Bolt
	};

	const iconOptions = [
		{ value: 'sparkles', label: 'Sparkles' },
		{ value: 'badge', label: 'Badge Check' },
		{ value: 'zap', label: 'Zap' }
	];

	let rows: EditablePlan[] = [];
	let selectedId = '';
	let editModalOpen = false;
	let loading = true;
	let error = '';
	let saving = false;
	let dirtyIds = new Set<string>();
	let selectedPlan: EditablePlan | undefined;
	let draftActiveDirty = false;
	let togglingIds = new Set<string>();

	const formatChatpoint = (micros?: number | null) =>
		((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2 });

	const normalizePlan = (plan: SubscriptionPlan): EditablePlan => {
		const features: SubscriptionFeatures =
			!Array.isArray(plan.features) && plan.features ? plan.features : {};
		return {
			...plan,
			plan_chatpoint: String((plan.plan_chatpoint_allowance_micros ?? 0) / 1_000_000),
			icon: features.icon ?? 'sparkles',
			subtitle: features.subtitle ?? '',
			highlightsText: (features.highlights ?? []).join('\n'),
			model_summary: features.model_summary ?? '',
			cta_label: features.cta_label ?? ''
		};
	};

	const iconFor = (icon: string) => iconMap[icon as keyof typeof iconMap] ?? Sparkles;

	const markDirty = (id: string | undefined) => {
		if (!id) return;
		dirtyIds = new Set(dirtyIds).add(id);
	};

	const openEditor = (id: string) => {
		const source = rows.find((plan) => plan.id === id);
		if (!source) return;
		selectedId = id;
		selectedPlan = {
			...source,
			features: source.features
				? {
						...source.features,
						highlights: source.features.highlights ? [...source.features.highlights] : undefined
					}
				: source.features
		};
		draftActiveDirty = false;
		editModalOpen = true;
	};

	const cancelEdit = () => {
		if (saving) return;
		if (selectedPlan) dirtyIds.delete(selectedPlan.id);
		dirtyIds = new Set(dirtyIds);
		selectedPlan = undefined;
		selectedId = '';
		draftActiveDirty = false;
		editModalOpen = false;
	};

	const load = async () => {
		loading = true;
		error = '';
		try {
			const plans = await getAdminSubscriptionPlans(localStorage.token);
			rows = (plans ?? []).map(normalizePlan);
			if (!rows.some((plan) => plan.id === selectedId)) selectedId = rows[0]?.id ?? '';
			dirtyIds = new Set();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
			rows = [];
			selectedId = '';
			toast.error(error);
		} finally {
			loading = false;
		}
	};

	const toggleActive = async (row: EditablePlan, nextState: boolean) => {
		if (togglingIds.has(row.id)) return;
		// The Switch binding applies the optimistic value before dispatching change.
		const previousState = !nextState;
		togglingIds = new Set(togglingIds).add(row.id);
		try {
			const updated = await updateAdminSubscriptionPlan(localStorage.token, row.id, {
				is_active: nextState
			});
			if (!updated) throw new Error('服务器未返回更新后的计划');
			const normalized = normalizePlan(updated);
			rows = rows.map((item) => (item.id === row.id ? normalized : item));
			dirtyIds.delete(row.id);
			dirtyIds = new Set(dirtyIds);
		} catch (cause) {
			rows = rows.map((item) =>
				item.id === row.id ? { ...item, is_active: previousState } : item
			);
			toast.error(cause instanceof Error ? cause.message : String(cause));
		} finally {
			togglingIds.delete(row.id);
			togglingIds = new Set(togglingIds);
		}
	};

	const save = async (row: EditablePlan | undefined) => {
		if (!row || saving) return;
		saving = true;
		const features: SubscriptionFeatures = {
			icon: row.icon || undefined,
			subtitle: row.subtitle || undefined,
			highlights: (row.highlightsText ?? '')
				.split('\n')
				.map((item) => item.trim())
				.filter(Boolean),
			model_summary: row.model_summary || undefined,
			cta_label: row.cta_label || undefined
		};

		try {
			const serverRow = rows.find((item) => item.id === row.id);
			const updated = await updateAdminSubscriptionPlan(localStorage.token, row.id, {
				display_name: row.display_name,
				description: row.description,
				plan_chatpoint: row.plan_chatpoint,
				period_days: Number(row.period_days),
				features,
				is_active: draftActiveDirty ? !!row.is_active : !!serverRow?.is_active
			});
			if (!updated) throw new Error('服务器未返回更新后的计划');
			rows = rows.map((item) => (item.id === row.id ? normalizePlan(updated) : item));
			dirtyIds.delete(row.id);
			dirtyIds = new Set(dirtyIds);
			toast.success('订阅计划已保存。');
			selectedPlan = undefined;
			selectedId = '';
			draftActiveDirty = false;
			editModalOpen = false;
		} catch (cause) {
			toast.error(cause instanceof Error ? cause.message : String(cause));
		} finally {
			saving = false;
		}
	};

	onMount(load);
</script>

<div class="flex flex-col gap-4" aria-busy={loading}>
	{#if loading}
		<div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
			{#each Array(3) as _}
				<div
					class="h-72 animate-pulse rounded-lg border border-gray-100 bg-gray-50 dark:border-gray-850 dark:bg-gray-900"
				></div>
			{/each}
		</div>
	{:else if error}
		<div
			class="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-700 dark:border-red-900/60 dark:bg-red-950/20 dark:text-red-300"
		>
			<div class="font-medium">订阅计划加载失败</div>
			<div class="mt-1 break-words">{error}</div>
			<button
				type="button"
				class="mt-3 rounded-lg bg-red-700 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-red-800"
				on:click={load}>重试</button
			>
		</div>
	{:else if rows.length === 0}
		<div
			class="rounded-lg border border-gray-100 bg-gray-50/40 p-4 text-xs text-gray-500 dark:border-gray-850 dark:bg-white/[0.02]"
		>
			暂无订阅计划。
		</div>
	{:else}
		<section>
			<div class="mb-2 flex items-center justify-between gap-3">
				<h3 class="text-xs text-gray-400 dark:text-gray-600">计划</h3>
				<span class="text-xs text-gray-500"
					>{rows.filter((plan) => plan.is_active).length} 个启用</span
				>
			</div>
			<div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
				{#each rows as row (row.id)}
					<article
						class="flex min-h-72 flex-col rounded-lg border border-gray-100 bg-white/40 p-3 transition hover:border-gray-300 dark:border-gray-850 dark:bg-white/[0.02] dark:hover:border-gray-700"
					>
						<div class="flex items-start justify-between gap-3">
							<div class="flex min-w-0 items-center gap-2">
								<span
									class="flex size-8 flex-none items-center justify-center rounded-lg bg-gray-100 text-gray-700 dark:bg-gray-850 dark:text-gray-200"
								>
									<svelte:component this={iconFor(row.icon)} className="size-4" />
								</span>
								<span class="min-w-0">
									<span class="block truncate text-[13px] font-medium text-gray-900 dark:text-white"
										>{row.display_name}</span
									>
									<span class="mt-0.5 block truncate text-[11px] text-gray-500"
										>{row.subtitle || row.description || '未设置说明'}</span
									>
								</span>
							</div>
							<Switch
								bind:state={row.is_active}
								ariaLabel={`${row.is_active ? '停用' : '启用'} ${row.display_name}`}
								on:change={(event) => toggleActive(row, event.detail)}
								disabled={togglingIds.has(row.id)}
							/>
						</div>

						<div class="mt-5 flex items-baseline gap-1.5 text-gray-900 dark:text-white">
							<span class="text-lg font-semibold"
								>{formatChatpoint(row.plan_chatpoint_allowance_micros)}</span
							>
							<span class="text-[11px] text-gray-500">Chatpoint / {row.period_days} 天</span>
						</div>

						<dl class="mt-4 space-y-2 text-[11px]">
							<div class="flex items-start justify-between gap-3">
								<dt class="text-gray-500">模型范围</dt>
								<dd class="max-w-[65%] text-right text-gray-700 dark:text-gray-300">
									{row.model_summary || '未设置'}
								</dd>
							</div>
							<div class="flex items-center justify-between gap-3">
								<dt class="text-gray-500">状态</dt>
								<dd class={row.is_active ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
									{row.is_active ? '启用' : '停用'}
								</dd>
							</div>
						</dl>

						{#if row.highlightsText}
							<ul class="mt-4 flex-1 space-y-1.5 text-[11px] text-gray-600 dark:text-gray-300">
								{#each row.highlightsText.split('\n').filter(Boolean).slice(0, 3) as highlight}
									<li class="flex gap-1.5">
										<span class="mt-1.5 size-1 rounded-full bg-green-500"></span><span
											>{highlight}</span
										>
									</li>
								{/each}
							</ul>
						{:else}
							<div class="flex-1"></div>
						{/if}

						<div class="mt-4 flex items-center justify-between gap-2">
							<span
								class="text-[11px] {dirtyIds.has(row.id)
									? 'text-amber-600 dark:text-amber-400'
									: 'text-gray-400'}"
							>
								{dirtyIds.has(row.id) ? '未保存' : '已同步'}
							</span>
							<button
								type="button"
								class="inline-flex h-7 items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 text-[11px] font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-850"
								on:click={() => openEditor(row.id)}
							>
								<Pencil className="size-3" />
								编辑计划
							</button>
						</div>
					</article>
				{/each}
			</div>
		</section>

		{#if selectedPlan && editModalOpen}
			<Modal
				size="md"
				bind:show={editModalOpen}
				closeOnBackdrop={false}
				closeOnEscape={false}
				className="rounded-lg bg-white dark:bg-gray-900"
			>
				<div class="w-full">
					<div
						class="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-gray-850"
					>
						<div class="text-sm font-medium text-gray-900 dark:text-white">
							{selectedPlan.display_name} 编辑计划
						</div>
					</div>
					<div class="max-h-[min(70vh,42rem)] overflow-y-auto px-4 py-3">
						<AdminSettingSection title="基本信息" first>
							<div class="grid gap-3 sm:grid-cols-2">
								<AdminSettingField label="计划名称" description="用户侧显示的套餐名称。">
									<input
										class="plan-input"
										bind:value={selectedPlan.display_name}
										on:input={() => markDirty(selectedPlan?.id)}
									/>
								</AdminSettingField>
								<AdminSettingField label="图标" description="用于计划卡片。">
									<select
										class="plan-input"
										bind:value={selectedPlan.icon}
										on:change={() => markDirty(selectedPlan?.id)}
									>
										{#each iconOptions as option}
											<option value={option.value}>{option.label}</option>
										{/each}
									</select>
								</AdminSettingField>
								<AdminSettingField label="周期天数" description="新订阅和周期重置使用的天数。">
									<input
										class="plan-input"
										type="number"
										min="1"
										bind:value={selectedPlan.period_days}
										on:input={() => markDirty(selectedPlan?.id)}
									/>
								</AdminSettingField>
								<AdminSettingField
									label="周期额度"
									description="按 Plan Chatpoint 计算的周期额度。"
								>
									<input
										class="plan-input"
										inputmode="decimal"
										min="0"
										bind:value={selectedPlan.plan_chatpoint}
										on:input={() => markDirty(selectedPlan?.id)}
									/>
								</AdminSettingField>
							</div>
							<AdminSettingRow
								label="计划状态"
								description="停用后不再用于新的订阅，不影响已有用户快照。"
							>
								<Switch
									bind:state={selectedPlan.is_active}
									ariaLabel="启用计划"
									on:change={() => {
										draftActiveDirty = true;
										markDirty(selectedPlan?.id);
									}}
								/>
							</AdminSettingRow>
						</AdminSettingSection>

						<AdminSettingSection title="展示内容">
							<AdminSettingField label="副标题" description="显示在计划名称下方的简短说明。">
								<input
									class="plan-input"
									bind:value={selectedPlan.subtitle}
									on:input={() => markDirty(selectedPlan?.id)}
								/>
							</AdminSettingField>
							<AdminSettingField label="按钮文案" description="用户订阅卡片的操作文案。">
								<input
									class="plan-input"
									bind:value={selectedPlan.cta_label}
									on:input={() => markDirty(selectedPlan?.id)}
								/>
							</AdminSettingField>
							<AdminSettingField label="模型说明" description="概括当前计划可用的模型范围。">
								<input
									class="plan-input"
									bind:value={selectedPlan.model_summary}
									on:input={() => markDirty(selectedPlan?.id)}
								/>
							</AdminSettingField>
							<AdminSettingField label="计划介绍" description="支持多行文本，显示在用户订阅页。">
								<textarea
									class="plan-textarea"
									bind:value={selectedPlan.description}
									on:input={() => markDirty(selectedPlan?.id)}
								></textarea>
							</AdminSettingField>
							<AdminSettingField label="功能亮点" description="每行一条，卡片最多预览三条。">
								<textarea
									class="plan-textarea min-h-24"
									bind:value={selectedPlan.highlightsText}
									on:input={() => markDirty(selectedPlan?.id)}
								></textarea>
							</AdminSettingField>
						</AdminSettingSection>
					</div>
					<div
						class="flex items-center justify-end gap-2 border-t border-gray-100 px-4 py-3 dark:border-gray-850"
					>
						{#if dirtyIds.has(selectedPlan.id)}
							<span class="mr-auto text-[11px] text-amber-600 dark:text-amber-400"
								>有未保存修改</span
							>
						{/if}
						<button
							type="button"
							class="h-7 rounded-lg px-2.5 text-[11px] text-gray-500 transition hover:bg-gray-100 dark:hover:bg-gray-850"
							on:click={cancelEdit}>取消</button
						>
						<button
							type="button"
							class="inline-flex h-7 items-center gap-1.5 rounded-lg bg-gray-900 px-2.5 text-[11px] font-medium text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
							disabled={saving || !dirtyIds.has(selectedPlan.id)}
							on:click={() => save(selectedPlan)}
						>
							<CheckCircle className="size-3.5" />
							{saving ? '保存中…' : '保存修改'}
						</button>
					</div>
				</div>
			</Modal>
		{/if}
	{/if}
</div>

<style>
	.plan-input,
	.plan-textarea {
		width: 100%;
		border: 1px solid rgb(229 231 235 / 0.8);
		border-radius: 8px;
		background: rgb(249 250 251 / 0.55);
		padding: 0 9px;
		font-size: 0.75rem;
		line-height: 1.25rem;
		color: rgb(55 65 81);
		outline: none;
		transition: border-color 120ms ease;
	}

	.plan-input {
		height: 28px;
	}

	.plan-textarea {
		min-height: 68px;
		padding-top: 5px;
		padding-bottom: 5px;
		resize: vertical;
	}

	.plan-input:focus,
	.plan-textarea:focus {
		border-color: rgb(156 163 175);
	}

	:global(.dark) .plan-input,
	:global(.dark) .plan-textarea {
		border-color: rgb(55 65 81 / 0.8);
		background: rgb(17 24 39 / 0.55);
		color: rgb(229 231 235);
	}

	:global(.dark) .plan-input:focus,
	:global(.dark) .plan-textarea:focus {
		border-color: rgb(107 114 128);
	}
</style>
