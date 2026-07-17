<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { getModelMarketplace, type MarketplaceModel } from '$lib/apis/models';
	import { mobile, showSidebar } from '$lib/stores';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ModelCallChart from '$lib/components/models/ModelCallChart.svelte';

	let loading = true;
	let query = '';
	let expandedModelId = '';
	let marketplaceModels: MarketplaceModel[] = [];

	const tierLabels: Record<string, string> = {
		free: 'Free',
		plus: 'Plus',
		chatpower: 'ChatPower'
	};

	$: visibleModels = marketplaceModels.filter((model) => {
		const term = query.trim().toLowerCase();
		return (
			!term ||
			model.name.toLowerCase().includes(term) ||
			model.id.toLowerCase().includes(term) ||
			model.description.toLowerCase().includes(term)
		);
	});

	const load = async () => {
		loading = true;
		marketplaceModels = await getModelMarketplace(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return [];
		});
		loading = false;
	};

	const priceLabel = (model: MarketplaceModel) => {
		if (model.quota_mode === 'unlimited') return '无限使用';
		return `输入 ${model.pricing.input} / 输出 ${model.pricing.output} CP`;
	};

	onMount(load);
</script>

<svelte:head><title>模型广场</title></svelte:head>

<div
	class="flex h-screen max-h-[100dvh] w-full flex-1 flex-col overflow-hidden transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: 'md:max-w-[calc(100%-49px)]'}"
>
	<header
		class="flex min-h-12 items-center gap-2 border-b border-gray-100 px-3 dark:border-gray-850 sm:px-5"
	>
		{#if $mobile}
			<Tooltip content={$showSidebar ? '关闭侧栏' : '打开侧栏'}>
				<button
					class="flex size-8 items-center justify-center rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850"
					on:click={() => showSidebar.set(!$showSidebar)}
					aria-label={$showSidebar ? '关闭侧栏' : '打开侧栏'}
				>
					<SidebarIcon />
				</button>
			</Tooltip>
		{/if}
		<div class="font-medium">模型广场</div>
		<div
			class="ml-auto flex min-w-0 max-w-72 flex-1 items-center gap-2 rounded-lg bg-gray-100 px-3 py-1.5 dark:bg-gray-850"
		>
			<Search className="size-4" />
			<input
				class="min-w-0 flex-1 bg-transparent text-sm outline-none"
				bind:value={query}
				placeholder="搜索模型"
				aria-label="搜索模型"
			/>
		</div>
	</header>

	<main class="flex-1 overflow-y-auto px-3 py-5 sm:px-6">
		<div class="mx-auto w-full max-w-6xl">
			{#if loading}
				<div class="flex justify-center py-16"><Spinner className="size-5" /></div>
			{:else if !visibleModels.length}
				<div
					class="border-y border-gray-100 py-16 text-center text-sm text-gray-500 dark:border-gray-850"
				>
					暂无可展示模型
				</div>
			{:else}
				<div class="grid items-start gap-3 md:grid-cols-2 xl:grid-cols-3">
					{#each visibleModels as model (model.id)}
						<article
							class="overflow-hidden rounded-lg border border-gray-100 bg-white dark:border-gray-850 dark:bg-gray-900"
						>
							<button
								type="button"
								class="flex w-full flex-col p-4 text-left"
								aria-expanded={expandedModelId === model.id}
								on:click={() => (expandedModelId = expandedModelId === model.id ? '' : model.id)}
							>
								<div class="flex w-full items-start gap-3">
									<img
										class="size-11 flex-none rounded-lg object-cover"
										src={`${WEBUI_API_BASE_URL}/models/model/profile/image?id=${encodeURIComponent(model.id)}`}
										alt={model.name}
									/>
									<div class="min-w-0 flex-1">
										<div class="flex items-center gap-2">
											<h2 class="truncate font-medium text-gray-900 dark:text-gray-100">
												{model.name}
											</h2>
											<span
												class="size-2 flex-none rounded-full {model.is_active
													? 'bg-emerald-500'
													: 'bg-gray-300 dark:bg-gray-700'}"
												title={model.is_active ? '运行中' : '已停用'}
											></span>
										</div>
										<div class="mt-0.5 truncate text-xs text-gray-400">{model.id}</div>
									</div>
									<span class="text-gray-400" aria-hidden="true"
										>{expandedModelId === model.id ? '−' : '+'}</span
									>
								</div>
								<p
									class="mt-3 line-clamp-3 min-h-15 text-sm leading-5 text-gray-600 dark:text-gray-300"
								>
									{model.description || '暂无简介'}
								</p>
								<div class="mt-4 flex flex-wrap gap-1.5">
									{#each model.allowed_tiers as tier}<span
											class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-850 dark:text-gray-300"
											>{tierLabels[tier] ?? tier}</span
										>{/each}
									{#if model.restricted_access}<span
											class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-850 dark:text-gray-300"
											>指定权限</span
										>{/if}
								</div>
								<div class="mt-3 text-xs text-gray-500">{priceLabel(model)} / 1M Token</div>
							</button>

							{#if expandedModelId === model.id}
								<div class="border-t border-gray-100 px-4 py-4 dark:border-gray-850">
									<div
										class="whitespace-pre-wrap text-sm leading-6 text-gray-700 dark:text-gray-300"
									>
										{model.long_description || model.description || '暂无详细介绍'}
									</div>
									<div
										class="mt-5 grid grid-cols-2 gap-x-4 gap-y-2 border-y border-gray-100 py-3 text-xs dark:border-gray-850"
									>
										<div>
											<span class="text-gray-500">输入</span>
											<div class="mt-1 font-medium">{model.pricing.input} CP</div>
										</div>
										<div>
											<span class="text-gray-500">输出</span>
											<div class="mt-1 font-medium">{model.pricing.output} CP</div>
										</div>
										<div>
											<span class="text-gray-500">创建缓存</span>
											<div class="mt-1 font-medium">{model.pricing.cache_creation} CP</div>
										</div>
										<div>
											<span class="text-gray-500">读取缓存</span>
											<div class="mt-1 font-medium">{model.pricing.cache_read} CP</div>
										</div>
									</div>
									<div class="mt-4 text-xs font-medium text-gray-500">近 30 天调用量</div>
									<ModelCallChart history={model.history} />
								</div>
							{/if}
						</article>
					{/each}
				</div>
			{/if}
		</div>
	</main>
</div>
