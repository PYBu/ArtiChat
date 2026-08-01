<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getBackendConfig } from '$lib/apis';
	import { getPlatformSettings, setPlatformSettings, uploadPlatformLogo } from '$lib/apis/platform';
	import { config, WEBUI_NAME } from '$lib/stores';
	import SidebarLinkIcon from '$lib/components/layout/Sidebar/SidebarLinkIcon.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import AdminSettingField from './AdminSettingField.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import AdminSettingSection from './AdminSettingSection.svelte';

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
	const logoFields: Array<{
		theme: 'light' | 'dark';
		label: string;
		key: 'logo_light' | 'logo_dark';
	}> = [
		{ theme: 'light', label: '亮色模式 Logo', key: 'logo_light' },
		{ theme: 'dark', label: '暗色模式 Logo', key: 'logo_dark' }
	];
	const inputClass =
		'w-full h-7 rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';
	const textareaClass =
		'w-full resize-y rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';
	const selectClass =
		'h-7 min-w-0 rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500';

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

<form class="flex h-full flex-col justify-between text-sm" on:submit|preventDefault={save}>
	<h2 class="mb-4 text-sm font-medium text-gray-900 dark:text-white">平台设置</h2>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		<AdminSettingSection title="品牌" first>
			<AdminSettingField label="平台名称" description="用于页面标题、侧边栏和系统邮件。">
				<input class={inputClass} bind:value={settings.name} />
			</AdminSettingField>

			<div class="grid gap-3 sm:grid-cols-2">
				{#each logoFields as item}
					<AdminSettingField label={item.label} description="支持 PNG、JPEG 或 WebP。">
						<div class="flex items-center gap-2">
							<div
								class="flex size-8 shrink-0 items-center justify-center rounded-lg border border-gray-100/60 bg-gray-50/40 dark:border-white/[0.06] dark:bg-white/[0.03]"
							>
								{#if settings[item.key]}
									<img class="size-6 object-contain" src={settings[item.key]} alt={item.label} />
								{:else}
									<span class="text-[0.625rem] text-gray-400">未设置</span>
								{/if}
							</div>
							<label
								class="inline-flex h-7 cursor-pointer items-center rounded-lg border border-gray-200 px-2.5 text-[0.6875rem] text-gray-600 transition hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-900"
							>
								更换
								<input
									class="sr-only"
									type="file"
									accept="image/png,image/jpeg,image/webp"
									on:change={(event) => upload(item.theme, event)}
								/>
							</label>
						</div>
					</AdminSettingField>
				{/each}
			</div>
		</AdminSettingSection>

		<AdminSettingSection title="公开信息">
			<AdminSettingField label="About 标题" description="显示在关于页面的标题。">
				<input class={inputClass} bind:value={settings.about_title} />
			</AdminSettingField>
			<AdminSettingField label="About 内容" description="支持多行文本。">
				<textarea rows="6" class={textareaClass} bind:value={settings.about_content}></textarea>
			</AdminSettingField>
		</AdminSettingSection>

		<AdminSettingSection title="主页入口">
			<AdminSettingRow label="自定义菜单按钮" description="显示在新对话和搜索下方，最多 8 个。">
				<button
					type="button"
					class="flex size-7 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-gray-850 dark:hover:text-white"
					disabled={settings.sidebar_buttons.length >= 8}
					on:click={addSidebarButton}
					aria-label="新增主页菜单按钮"
					title="新增主页菜单按钮"><Plus className="size-4" /></button
				>
			</AdminSettingRow>

			{#if settings.sidebar_buttons.length}
				{#each settings.sidebar_buttons as button, index}
					<AdminSettingField
						label={`菜单按钮 ${index + 1}`}
						description="填写名称和站内路径或外部链接。"
					>
						<div class="grid min-w-0 gap-2 sm:grid-cols-[minmax(7rem,0.8fr)_minmax(8rem,1fr)_auto]">
							<div class="flex min-w-0 items-center gap-1.5">
								<SidebarLinkIcon icon={button.icon} className="size-4 shrink-0" />
								<select class={selectClass + ' flex-1'} bind:value={button.icon} aria-label="图标">
									{#each iconOptions as option}
										<option value={option.value}>{option.label}</option>
									{/each}
								</select>
							</div>
							<input
								class={inputClass}
								maxlength="40"
								bind:value={button.name}
								placeholder="名称"
								aria-label="菜单名称"
							/>
							<div class="flex min-w-0 items-center gap-1.5">
								<input
									class={inputClass}
									bind:value={button.url}
									placeholder="/path 或 https://example.com"
									aria-label="菜单 URL"
								/>
								<button
									type="button"
									class="flex size-7 shrink-0 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-100 hover:text-red-600 dark:hover:bg-gray-850"
									on:click={() => removeSidebarButton(index)}
									aria-label="删除菜单按钮"
									title="删除菜单按钮"><XMark className="size-4" /></button
								>
							</div>
						</div>
					</AdminSettingField>
				{/each}
			{:else}
				<div class="text-[0.6875rem] text-gray-400 dark:text-gray-600">暂无自定义按钮。</div>
			{/if}
		</AdminSettingSection>
	</div>

	<div class="mt-4 flex justify-end">
		<button
			type="submit"
			class="h-7 rounded-lg bg-black px-3 text-xs font-medium text-white transition hover:bg-gray-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-gray-200"
			disabled={saving}>{saving ? '保存中...' : '保存更改'}</button
		>
	</div>
</form>
