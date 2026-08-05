<script lang="ts">
	import { toast } from 'svelte-sonner';

	import Switch from '$lib/components/common/Switch.svelte';
	import ArrowPath from '$lib/components/icons/ArrowPath.svelte';
	import Cloud from '$lib/components/icons/Cloud.svelte';
	import CloudArrowUp from '$lib/components/icons/CloudArrowUp.svelte';
	import Component from '$lib/components/icons/Component.svelte';
	import InfoCircle from '$lib/components/icons/InfoCircle.svelte';
	import Search from '$lib/components/icons/Search.svelte';

	type PluginFilter = 'all' | 'installed';

	const plugins = [
		{
			id: 'email-tool',
			title: '邮箱助手',
			developer: 'ArtiVis Labs',
			description: '邮箱工具正在开发，当前不可启用。',
			version: '0.1.0-dev',
			updated: '开发中',
			category: '模型工具',
			status: 'development',
			icon: Component
		}
	];

	let filter: PluginFilter = 'all';
	let query = '';
	let syncing = false;
	let autoSync = false;
	let allowUserUploads = false;
	let uploadedFileName = '';
	let installedPlugins: Record<string, boolean> = {};
	let uploadInput: HTMLInputElement;
	let filteredPlugins = plugins;

	$: filteredPlugins = plugins.filter((plugin) => {
		const normalizedQuery = query.trim().toLowerCase();
		const matchesQuery =
			!normalizedQuery ||
			[plugin.title, plugin.developer, plugin.description, plugin.category].some((value) =>
				value.toLowerCase().includes(normalizedQuery)
			);
		const matchesFilter =
			filter === 'all' || (filter === 'installed' && installedPlugins[plugin.id]);
		return matchesQuery && matchesFilter;
	});

	const syncCatalog = async () => {
		if (syncing) return;
		syncing = true;
		await new Promise((resolve) => setTimeout(resolve, 450));
		syncing = false;
		toast.info('ACPlugin 当前未连接');
	};

	const handleUpload = (event: Event) => {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		uploadedFileName = file.name;
		toast.info('插件仅对当前用户可用');
		input.value = '';
	};
</script>

<svelte:head>
	<title>插件中心 / ArtiChat</title>
</svelte:head>

<div class="operations-page mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6">
	<header
		class="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 pb-3 dark:border-gray-850"
	>
		<div class="min-w-0">
			<div class="flex items-center gap-2">
				<a
					href="/admin/subscriptions"
					class="inline-flex size-7 shrink-0 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-850 dark:hover:text-white"
					aria-label="返回运营管理"
					title="返回运营管理"
				>
					<span aria-hidden="true">←</span>
				</a>
				<div>
					<h1 class="text-[14px] font-medium text-gray-900 dark:text-gray-100">插件中心</h1>
					<p class="mt-0.5 text-[11px] text-gray-500">
						管理 ACPlugin 目录、个人上传内容和插件开关。
					</p>
				</div>
			</div>
		</div>
		<div class="flex shrink-0 items-center gap-1.5">
			<input
				bind:this={uploadInput}
				type="file"
				accept=".zip,.tar,.gz,.json"
				hidden
				on:change={handleUpload}
			/>
			<button
				type="button"
				class="inline-flex h-7 items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 text-[11px] font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-850"
				on:click={() => uploadInput?.click()}
			>
				<CloudArrowUp className="size-3.5" />
				上传插件
			</button>
			<button
				type="button"
				class="inline-flex h-7 items-center gap-1.5 rounded-lg bg-black px-2.5 text-[11px] font-medium text-white transition hover:bg-gray-800 disabled:cursor-wait disabled:opacity-60 dark:bg-white dark:text-black dark:hover:bg-gray-200"
				on:click={syncCatalog}
				disabled={syncing}
			>
				<ArrowPath class="size-3.5 {syncing ? 'animate-spin' : ''}" />
				{syncing ? '同步中' : '立即同步'}
			</button>
		</div>
	</header>

	<section class="grid gap-2 sm:grid-cols-3" aria-label="插件中心概览">
		<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
			<div class="text-[11px] text-gray-500">已安装插件</div>
			<div class="mt-1 text-lg font-medium text-gray-900 dark:text-gray-100">
				{Object.keys(installedPlugins).length}
			</div>
			<div class="mt-0.5 text-[11px] text-gray-500">当前可在模型工具中使用</div>
		</div>
		<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
			<div class="text-[11px] text-gray-500">ACP 目录</div>
			<div class="mt-1 text-lg font-medium text-gray-900 dark:text-gray-100">0</div>
			<div class="mt-0.5 text-[11px] text-gray-500">当前未连接</div>
		</div>
		<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
			<div class="text-[11px] text-gray-500">个人上传</div>
			<div class="mt-1 text-lg font-medium text-gray-900 dark:text-gray-100">0</div>
			<div class="mt-0.5 text-[11px] text-gray-500">
				{uploadedFileName || '仅当前用户可用'}
			</div>
		</div>
	</section>

	<section class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div class="flex min-w-0 items-start gap-2.5">
				<div
					class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-700 dark:bg-gray-850 dark:text-gray-200"
				>
					<Cloud className="size-4" />
				</div>
				<div class="min-w-0">
					<div class="flex flex-wrap items-center gap-2">
						<h2 class="text-[13px] font-medium text-gray-900 dark:text-gray-100">ACPlugin</h2>
						<span
							class="rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-900 dark:text-gray-300"
							>未连接</span
						>
					</div>
					<p class="mt-0.5 text-[11px] text-gray-500">ACPlugin 目录当前未连接。</p>
				</div>
			</div>
			<div class="flex shrink-0 items-center gap-4 text-[11px] text-gray-500">
				<label class="flex items-center gap-2">
					<span>自动同步</span>
					<Switch bind:state={autoSync} ariaLabel="自动同步插件目录" />
				</label>
				<label class="flex items-center gap-2">
					<span>允许个人上传</span>
					<Switch bind:state={allowUserUploads} ariaLabel="允许个人上传插件" />
				</label>
			</div>
		</div>
	</section>

	<section>
		<div class="mb-2 flex flex-wrap items-center justify-between gap-2">
			<div
				class="flex items-center gap-1 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900"
				role="tablist"
				aria-label="插件筛选"
			>
				{#each [{ id: 'all', label: '全部插件' }, { id: 'installed', label: '已安装' }] as item}
					<button
						type="button"
						role="tab"
						aria-selected={filter === item.id}
						class="h-7 rounded-md px-2.5 text-[11px] transition {filter === item.id
							? 'bg-white font-medium text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white'
							: 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}"
						on:click={() => (filter = item.id as PluginFilter)}
					>
						{item.label}
					</button>
				{/each}
			</div>
			<label
				class="flex h-7 min-w-52 items-center gap-1.5 rounded-lg bg-gray-50 px-2 text-[11px] text-gray-500 dark:bg-gray-900"
			>
				<Search className="size-3.5 shrink-0" />
				<span class="sr-only">搜索插件</span>
				<input
					class="min-w-0 flex-1 bg-transparent outline-hidden"
					bind:value={query}
					placeholder="搜索插件"
				/>
			</label>
		</div>

		<div class="grid gap-2 lg:grid-cols-2">
			{#each filteredPlugins as plugin (plugin.id)}
				<article
					class="flex min-w-0 flex-col rounded-lg border border-gray-100 p-3 transition hover:border-gray-200 dark:border-gray-850 dark:hover:border-gray-700"
				>
					<div class="flex items-start justify-between gap-3">
						<div class="flex min-w-0 items-start gap-2.5">
							<div
								class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-700 dark:bg-gray-850 dark:text-gray-200"
							>
								<svelte:component this={plugin.icon} className="size-4" />
							</div>
							<div class="min-w-0">
								<div class="flex min-w-0 flex-wrap items-center gap-1.5">
									<h3 class="truncate text-[13px] font-medium text-gray-900 dark:text-gray-100">
										{plugin.title}
									</h3>
									<span
										class="rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-900"
										>{plugin.category}</span
									>
								</div>
								<div class="mt-0.5 text-[11px] text-gray-500">
									{plugin.developer} · v{plugin.version}
								</div>
							</div>
						</div>
						{#if plugin.status === 'installed'}
							<span
								class="shrink-0 rounded-md bg-green-50 px-1.5 py-0.5 text-[10px] font-medium text-green-700 dark:bg-green-950/30 dark:text-green-300"
								>已安装</span
							>
						{:else if plugin.status === 'development'}
							<span
								class="shrink-0 rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-900 dark:text-gray-300"
								>开发中</span
							>
						{:else}
							<span
								class="shrink-0 rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-gray-900 dark:text-gray-300"
								>可安装</span
							>
						{/if}
					</div>
					<p class="mt-3 min-h-8 text-[11px] leading-4 text-gray-600 dark:text-gray-300">
						{plugin.description}
					</p>
					<div
						class="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-2.5 dark:border-gray-850"
					>
						<span class="text-[10px] text-gray-400">更新于 {plugin.updated}</span>
						<div class="flex items-center gap-2">
							{#if plugin.status === 'development'}
								<button
									type="button"
									class="h-7 cursor-not-allowed rounded-lg border border-gray-200 px-2.5 text-[11px] font-medium text-gray-400 dark:border-gray-700 dark:text-gray-500"
									disabled
								>
									开发中
								</button>
							{/if}
						</div>
					</div>
				</article>
			{:else}
				<div
					class="col-span-full rounded-lg border border-dashed border-gray-200 p-8 text-center text-[11px] text-gray-500 dark:border-gray-800"
				>
					没有匹配的插件
				</div>
			{/each}
		</div>
	</section>

	<section
		class="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50/50 p-3 text-[11px] text-blue-800 dark:border-blue-900/50 dark:bg-blue-950/10 dark:text-blue-200"
	>
		<InfoCircle className="mt-0.5 size-3.5 shrink-0" />
		<div>
			<div class="font-medium">插件安全边界</div>
			<div class="mt-0.5 leading-4 text-blue-700/80 dark:text-blue-200/80">
				ArtiChat 插件功能属于内测项，可能存在优化问题。ACPlugin
				提供的项目均已验证，自行加载插件需谨慎。
			</div>
		</div>
	</section>
</div>
