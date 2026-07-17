<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Switch from '$lib/components/common/Switch.svelte';
	import RegistrationSettings from '$lib/components/admin/Registration/RegistrationSettings.svelte';
	import EmailSettings from '$lib/components/admin/Email/EmailSettings.svelte';
	import EmailTemplates from '$lib/components/admin/Email/EmailTemplates.svelte';
	import EmailDeliveries from '$lib/components/admin/Email/EmailDeliveries.svelte';
	import {
		getEmailSettings,
		updateEmailSettings,
		type EmailSettings as EmailSettingsValue
	} from '$lib/apis/emails';

	type Section = 'registration' | 'settings' | 'templates' | 'deliveries';

	const sections: Array<{ id: Section; label: string }> = [
		{ id: 'registration', label: '注册与验证' },
		{ id: 'settings', label: '发信服务' },
		{ id: 'templates', label: '邮件模板' },
		{ id: 'deliveries', label: '发送记录' }
	];

	let section: Section = 'registration';
	let loading = true;
	let toggling = false;
	let emailSettings: EmailSettingsValue | null = null;

	const load = async () => {
		loading = true;
		emailSettings = await getEmailSettings(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		loading = false;
	};

	const setEmailEnabled = async (enabled: boolean) => {
		if (!emailSettings) return;
		toggling = true;
		const payload = { ...emailSettings, enabled } as Partial<EmailSettingsValue>;
		delete payload.password_configured;
		const saved = await updateEmailSettings(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (saved) {
			emailSettings = saved;
			if (!saved.enabled) section = 'registration';
			toast.success(saved.enabled ? '邮箱功能已启用。' : '邮箱功能已关闭。');
		}
		toggling = false;
	};

	onMount(load);
</script>

<div class="flex max-w-5xl flex-col gap-5">
	<div
		class="flex flex-col gap-4 border-b border-gray-100 pb-4 dark:border-gray-850 sm:flex-row sm:items-center sm:justify-between"
	>
		<div>
			<div class="text-base font-medium">邮箱</div>
			<div class="mt-1 text-xs text-gray-500">管理注册范围、邮箱验证与平台发信服务。</div>
		</div>
		{#if emailSettings}
			<div class="flex items-center justify-between gap-4 sm:justify-end">
				<span class="text-sm">启用邮箱功能</span>
				<Switch
					state={emailSettings.enabled}
					disabled={toggling}
					ariaLabel="启用邮箱功能"
					on:change={(event) => setEmailEnabled(event.detail)}
				/>
			</div>
		{/if}
	</div>

	{#if loading}
		<div class="py-8 text-sm text-gray-500">加载中...</div>
	{:else if emailSettings}
		<nav
			class="flex gap-1 overflow-x-auto border-b border-gray-100 pb-2 text-sm dark:border-gray-850"
			aria-label="邮箱设置"
		>
			{#each sections as item}
				<button
					type="button"
					class="min-w-fit rounded-lg px-3 py-1.5 transition {section === item.id
						? 'bg-gray-100 font-medium text-gray-900 dark:bg-gray-850 dark:text-white'
						: 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}"
					disabled={!emailSettings.enabled && item.id !== 'registration'}
					on:click={() => (section = item.id)}
				>
					{item.label}
				</button>
			{/each}
		</nav>

		{#if section === 'registration'}
			<RegistrationSettings embedded emailEnabled={emailSettings.enabled} />
		{:else if emailSettings.enabled && section === 'settings'}
			<EmailSettings showEnableToggle={false} />
		{:else if emailSettings.enabled && section === 'templates'}
			<EmailTemplates />
		{:else if emailSettings.enabled && section === 'deliveries'}
			<EmailDeliveries />
		{/if}
	{/if}
</div>
