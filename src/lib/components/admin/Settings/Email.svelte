<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Switch from '$lib/components/common/Switch.svelte';
	import RegistrationSettings from '$lib/components/admin/Registration/RegistrationSettings.svelte';
	import EmailSettings from '$lib/components/admin/Email/EmailSettings.svelte';
	import EmailTemplates from '$lib/components/admin/Email/EmailTemplates.svelte';
	import EmailDeliveries from '$lib/components/admin/Email/EmailDeliveries.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import AdminSettingSection from './AdminSettingSection.svelte';
	import {
		getEmailSettings,
		updateEmailSettings,
		type EmailSettings as EmailSettingsValue
	} from '$lib/apis/emails';

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
		if (!emailSettings || toggling) return;
		toggling = true;
		const payload = { ...emailSettings, enabled } as Partial<EmailSettingsValue>;
		delete payload.password_configured;
		delete payload.configured;
		const saved = await updateEmailSettings(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (saved) {
			emailSettings = saved;
			toast.success(saved.enabled ? '邮箱功能已启用。' : '邮箱功能已关闭。');
		}
		toggling = false;
	};

	onMount(load);
</script>

<div class="flex h-full flex-col justify-between text-sm">
	<h2 class="mb-4 text-sm font-medium text-gray-900 dark:text-white">电子邮箱</h2>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		{#if loading}
			<div class="py-8 text-sm text-gray-500">加载中...</div>
		{:else if emailSettings}
			<AdminSettingSection title="状态" first>
				<AdminSettingRow
					label="启用邮箱功能"
					description="用于验证码、密码重置、账户通知和订阅变更通知。"
					let:labelId
				>
					<Switch
						state={emailSettings.enabled}
						ariaLabelledbyId={labelId}
						on:change={(event) => setEmailEnabled(event.detail)}
					/>
				</AdminSettingRow>
			</AdminSettingSection>

			<RegistrationSettings embedded emailEnabled={emailSettings.enabled && emailSettings.configured} />

			{#if emailSettings.enabled}
				<EmailSettings showEnableToggle={false} />
				<EmailTemplates />
				<EmailDeliveries />
			{:else}
				<AdminSettingSection title="邮箱功能">
					<AdminSettingRow
						label="发信服务"
						description="启用邮箱功能后可配置 SMTP 连接、邮件模板和发送记录。"
					>
						<span class="text-xs text-gray-400 dark:text-gray-600">未启用</span>
					</AdminSettingRow>
				</AdminSettingSection>
			{/if}
		{/if}
	</div>
</div>
