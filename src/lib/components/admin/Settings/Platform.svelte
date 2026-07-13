<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getBackendConfig } from '$lib/apis';
	import { getPlatformSettings, setPlatformSettings, uploadPlatformLogo } from '$lib/apis/configs';
	import { config, WEBUI_NAME } from '$lib/stores';

	let settings = { name: 'ArtiChat', about_title: '', about_content: '', logo_light: '', logo_dark: '' };
	let saving = false;

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
	<div><div class="text-base font-medium">平台设置</div><div class="text-xs text-gray-500">管理全局名称、主题 Logo 和用户 About 内容。</div></div>
	<label class="flex flex-col gap-1"><span class="text-xs text-gray-500">平台名称</span><input class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850" bind:value={settings.name} /></label>
	<div class="grid gap-4 md:grid-cols-2">
		{#each [{ theme: 'light', label: '亮色模式 Logo', key: 'logo_light' }, { theme: 'dark', label: '暗色模式 Logo', key: 'logo_dark' }] as item}
			<label class="flex flex-col gap-2"><span class="text-xs text-gray-500">{item.label}</span><div class="flex h-24 items-center justify-center border border-gray-100 dark:border-gray-850"><img class="max-h-16 max-w-full" src={settings[item.key]} alt={item.label} /></div><input type="file" accept="image/png,image/jpeg,image/webp" on:change={(event) => upload(item.theme, event)} /></label>
		{/each}
	</div>
	<label class="flex flex-col gap-1"><span class="text-xs text-gray-500">About Title</span><input class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850" bind:value={settings.about_title} /></label>
	<label class="flex flex-col gap-1"><span class="text-xs text-gray-500">About 内容</span><textarea rows="8" class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850" bind:value={settings.about_content}></textarea></label>
	<div><button type="button" class="rounded-lg bg-black px-4 py-2 text-sm text-white dark:bg-white dark:text-black" disabled={saving} on:click={save}>{saving ? '保存中...' : '保存更改'}</button></div>
</div>
