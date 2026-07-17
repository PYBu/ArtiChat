<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getBackendConfig } from '$lib/apis';
	import { getPlatformSettings, setPlatformSettings, uploadPlatformLogo } from '$lib/apis/configs';
	import { config, WEBUI_NAME } from '$lib/stores';
	import SidebarLinkIcon from '$lib/components/layout/Sidebar/SidebarLinkIcon.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	type SidebarButton = { name: string; url: string; icon: string };
	let settings: {
		name: string;
		about_title: string;
		about_content: string;
		logo_light: string;
		logo_dark: string;
		sidebar_buttons: SidebarButton[];
	} = {
		name: 'ArtiChat',
		about_title: '',
		about_content: '',
		logo_light: '',
		logo_dark: '',
		sidebar_buttons: []
	};
	let saving = false;

	const iconOptions = [
		{ value: 'link', label: '链接' },
		{ value: 'globe', label: '网站' },
		{ value: 'home', label: '主页' },
		{ value: 'document', label: '文档' },
		{ value: 'book', label: '知识库' },
		{ value: 'chat', label: '对话' },
		{ value: 'star', label: '收藏' },
		{ value: 'bolt', label: '快捷功能' },
		{ value: 'calendar', label: '日历' },
		{ value: 'cube', label: '服务' },
		{ value: 'grid', label: '应用' },
		{ value: 'help', label: '帮助' }
	];

	const addSidebarButton = () => {
		if (settings.sidebar_buttons.length >= 8) return;
		settings.sidebar_buttons = [...settings.sidebar_buttons, { name: '', url: '', icon: 'link' }];
	};

	const removeSidebarButton = (index: number) => {
		settings.sidebar_buttons = settings.sidebar_buttons.filter(
			(_, itemIndex) => itemIndex !== index
		);
	};

	const load = async () => {
		settings = await getPlatformSettings(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return settings;
		});
	};

	const upload = async (theme: 'light' | 'dark', event: Event) => {
		const file = (event.currentTarget as HTMLInputElement).files?.[0];
		if (!file) return;
		const result = await uploadPlatformLogo(localStorage.token, theme, file).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (result) {
			settings[theme === 'light' ? 'logo_light' : 'logo_dark'] = `${result.url}?v=${Date.now()}`;
			settings = { ...settings };
		}
	};

	const save = async () => {
		saving = true;
		const saved = await setPlatformSettings(localStorage.token, settings).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (saved) {
			settings = saved;
			const backendConfig = await getBackendConfig();
			config.set(backendConfig);
			WEBUI_NAME.set(backendConfig.name);
			toast.success('平台设置已保存。');
		}
		saving = false;
	};

	onMount(load);
</script>

<div class="flex max-w-3xl flex-col gap-5">
	<div>
		<div class="text-base font-medium">平台设置</div>
		<div class="text-xs text-gray-500">管理全局名称、主题 Logo 和用户 About 内容。</div>
	</div>
	<label class="flex flex-col gap-1"
		><span class="text-xs text-gray-500">平台名称</span><input
			class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
			bind:value={settings.name}
		/></label
	>
	<div class="grid gap-4 md:grid-cols-2">
		{#each [{ theme: 'light', label: '亮色模式 Logo', key: 'logo_light' }, { theme: 'dark', label: '暗色模式 Logo', key: 'logo_dark' }] as item}
			<label class="flex flex-col gap-2"
				><span class="text-xs text-gray-500">{item.label}</span>
				<div
					class="flex h-24 items-center justify-center border border-gray-100 dark:border-gray-850"
				>
					<img class="max-h-16 max-w-full" src={settings[item.key]} alt={item.label} />
				</div>
				<input
					type="file"
					accept="image/png,image/jpeg,image/webp"
					on:change={(event) => upload(item.theme, event)}
				/></label
			>
		{/each}
	</div>
	<label class="flex flex-col gap-1"
		><span class="text-xs text-gray-500">About Title</span><input
			class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
			bind:value={settings.about_title}
		/></label
	>
	<label class="flex flex-col gap-1"
		><span class="text-xs text-gray-500">About 内容</span><textarea
			rows="8"
			class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
			bind:value={settings.about_content}
		></textarea></label
	>
	<section class="flex flex-col gap-3 border-y border-gray-100 py-4 dark:border-gray-850">
		<div class="flex items-start justify-between gap-4">
			<div>
				<div class="font-medium">主页菜单按钮</div>
				<div class="mt-1 text-xs text-gray-500">显示在新对话和搜索下方，最多 8 个。</div>
			</div>
			<button
				type="button"
				class="flex size-8 items-center justify-center rounded-lg hover:bg-gray-100 disabled:opacity-40 dark:hover:bg-gray-850"
				disabled={settings.sidebar_buttons.length >= 8}
				on:click={addSidebarButton}
				aria-label="新增主页菜单按钮"
				title="新增主页菜单按钮"><Plus className="size-4" /></button
			>
		</div>
		{#if settings.sidebar_buttons.length}
			<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-850">
				{#each settings.sidebar_buttons as button, index}
					<div
						class="grid gap-2 py-3 sm:grid-cols-[9rem_minmax(8rem,1fr)_minmax(12rem,1.5fr)_2rem] sm:items-end"
					>
						<label class="flex min-w-0 flex-col gap-1"
							><span class="text-xs text-gray-500">图标</span>
							<div
								class="flex items-center gap-2 rounded-lg border border-gray-100 px-2 dark:border-gray-850"
							>
								<SidebarLinkIcon icon={button.icon} className="size-4" /><select
									class="min-w-0 flex-1 bg-transparent py-2 text-sm outline-none"
									bind:value={button.icon}
									>{#each iconOptions as option}<option value={option.value}>{option.label}</option
										>{/each}</select
								>
							</div></label
						>
						<label class="flex min-w-0 flex-col gap-1"
							><span class="text-xs text-gray-500">名称</span><input
								class="min-w-0 rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-sm dark:border-gray-850"
								maxlength="40"
								bind:value={button.name}
							/></label
						>
						<label class="flex min-w-0 flex-col gap-1"
							><span class="text-xs text-gray-500">URL</span><input
								class="min-w-0 rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-sm dark:border-gray-850"
								placeholder="/path 或 https://example.com"
								bind:value={button.url}
							/></label
						>
						<button
							type="button"
							class="flex size-8 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-red-600 dark:hover:bg-gray-850"
							on:click={() => removeSidebarButton(index)}
							aria-label="删除菜单按钮"
							title="删除菜单按钮"><XMark className="size-4" /></button
						>
					</div>
				{/each}
			</div>
		{:else}
			<div class="text-sm text-gray-500">暂无自定义按钮。</div>
		{/if}
	</section>
	<div>
		<button
			type="button"
			class="rounded-lg bg-black px-4 py-2 text-sm text-white dark:bg-white dark:text-black"
			disabled={saving}
			on:click={save}>{saving ? '保存中...' : '保存更改'}</button
		>
	</div>
</div>
