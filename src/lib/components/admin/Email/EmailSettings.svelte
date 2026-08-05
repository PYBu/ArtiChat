<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import AdminSettingField from '$lib/components/admin/Settings/AdminSettingField.svelte';
	import AdminSettingRow from '$lib/components/admin/Settings/AdminSettingRow.svelte';
	import AdminSettingSection from '$lib/components/admin/Settings/AdminSettingSection.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import SettingsSelect from '$lib/components/common/SettingsSelect.svelte';
	import {
		getEmailSettings,
		sendEmailTest,
		testEmailConnection,
		updateEmailSettings,
		type EmailSettings
	} from '$lib/apis/emails';

	export let showEnableToggle = true;

	const defaults: EmailSettings = {
		enabled: false,
		configured: false,
		host: '',
		port: 587,
		username: '',
		password: '',
		password_configured: false,
		password_requires_reset: false,
		security: 'starttls',
		sender_email: '',
		sender_name: 'ArtiChat',
		reply_to: '',
		public_url: '',
		subscription_notifications: true
	};

	const errorLabels: Record<string, string> = {
		SMTP_HOST_REQUIRED: '请填写 SMTP 主机。',
		SMTP_SENDER_EMAIL_REQUIRED: '请填写发件人地址。',
		SMTP_CONNECTION_FAILED: '无法连接 SMTP 服务器，请检查主机、端口和网络。',
		SMTP_TLS_FAILED: 'TLS 握手失败，请检查安全模式和证书。',
		SMTP_AUTH_FAILED: 'SMTP 认证失败，请检查用户名和密码。',
		SMTP_PASSWORD_REQUIRED: '请输入 SMTP 密码。',
		SMTP_PASSWORD_REENTER_REQUIRED: '保存的 SMTP 密码无法读取，请重新输入密码并保存。',
		SMTP_SEND_FAILED: '邮件发送失败，请检查发件人权限和收件地址。'
	};

	let settings = { ...defaults };
	let loading = true;
	let saving = false;
	let testingConnection = false;
	let sendingTest = false;
	let testRecipient = '';

	const inputClass =
		'w-full h-7 rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';
	const actionButtonClass =
		'text-xs text-gray-500 transition-colors hover:text-gray-900 disabled:opacity-50 dark:text-gray-500 dark:hover:text-white';
	const primaryButtonClass =
		'h-7 rounded-lg bg-black px-3 text-xs font-medium text-white transition hover:bg-gray-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-gray-200';

	const showError = (error: unknown) => toast.error(errorLabels[String(error)] ?? String(error));

	const load = async () => {
		loading = true;
		settings = await getEmailSettings(localStorage.token).catch((error) => {
			showError(error);
			return settings;
		});
		loading = false;
	};

	const persist = async (notify = true) => {
		saving = true;
		const payload: Partial<EmailSettings> = { ...settings };
		delete payload.configured;
		delete payload.password_configured;
		delete payload.password_requires_reset;
		const saved = await updateEmailSettings(localStorage.token, payload).catch((error) => {
			showError(error);
			return null;
		});
		if (saved) {
			settings = saved;
			if (notify) toast.success('邮箱设置已保存。');
		}
		saving = false;
		return saved;
	};

	const checkConnection = async () => {
		testingConnection = true;
		const saved = await persist(false);
		if (saved) {
			const result = await testEmailConnection(localStorage.token).catch((error) => {
				showError(error);
				return null;
			});
			if (result?.ok) toast.success('SMTP 连接测试通过。');
		}
		testingConnection = false;
	};

	const sendTest = async () => {
		if (!testRecipient.trim()) {
			toast.error('请输入测试收件邮箱。');
			return;
		}
		sendingTest = true;
		const saved = await persist(false);
		if (saved) {
			const delivery = await sendEmailTest(localStorage.token, testRecipient.trim()).catch(
				(error) => {
					showError(error);
					return null;
				}
			);
			if (delivery?.status === 'sent') toast.success('测试邮件已发送。');
			else if (delivery?.status === 'failed') showError(delivery.error);
		}
		sendingTest = false;
	};

	onMount(load);
</script>

{#if loading}
	<div class="py-8 text-sm text-gray-500">加载中...</div>
{:else}
	<div class="flex w-full flex-col">
		<AdminSettingSection title="SMTP 连接" first>
			{#if showEnableToggle}
				<AdminSettingRow
					label="启用发信服务"
					description="启用 SMTP 后，系统才会发送注册、密码重置和订阅通知。"
					let:labelId
				>
					<Switch bind:state={settings.enabled} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
			{/if}
			<AdminSettingField label="SMTP 主机" description="SMTP 服务器的主机地址。">
				<input class={inputClass} bind:value={settings.host} autocomplete="off" />
			</AdminSettingField>
			<AdminSettingField label="端口" description="STARTTLS 通常使用 587；SSL/TLS 通常使用 465。">
				<input class={inputClass} type="number" min="1" max="65535" bind:value={settings.port} />
			</AdminSettingField>
			<AdminSettingRow label="安全模式" description="选择 SMTP 的加密与握手模式。">
				<SettingsSelect bind:value={settings.security}>
					<option value="starttls">STARTTLS</option>
					<option value="ssl">SSL/TLS</option>
					<option value="none">无加密</option>
				</SettingsSelect>
			</AdminSettingRow>
			<AdminSettingField label="用户名">
				<input class={inputClass} bind:value={settings.username} autocomplete="username" />
			</AdminSettingField>
			<AdminSettingField label="密码" description="密码不会回显；容器密钥变化时需重新输入。">
				<input
					type="password"
					class={inputClass}
					bind:value={settings.password}
					autocomplete="new-password"
				/>
				{#if settings.password_requires_reset}
					<div class="mt-1 text-[0.6875rem] text-amber-600 dark:text-amber-400">
						容器密钥已变化，请重新输入 SMTP 密码。
					</div>
				{/if}
			</AdminSettingField>
			<AdminSettingRow label="SMTP 连接测试" description="保存当前设置并检查服务器是否可达。">
				<button
					class={actionButtonClass}
					type="button"
					disabled={testingConnection || saving}
					on:click={checkConnection}
				>
					{testingConnection ? '测试中...' : '保存并测试连接'}
				</button>
			</AdminSettingRow>
		</AdminSettingSection>

		<AdminSettingSection title="发件信息">
			<AdminSettingField label="发件人地址">
				<input type="email" class={inputClass} bind:value={settings.sender_email} />
			</AdminSettingField>
			<AdminSettingField label="发件人名称">
				<input class={inputClass} bind:value={settings.sender_name} />
			</AdminSettingField>
			<AdminSettingField label="Reply-To" description="可选，用于接收回复邮件。">
				<input type="email" class={inputClass} bind:value={settings.reply_to} />
			</AdminSettingField>
			<AdminSettingField label="平台访问地址" description="用于邮件中的重置链接和设置回路。">
				<input type="url" class={inputClass} bind:value={settings.public_url} />
			</AdminSettingField>
			<AdminSettingRow
				label="订阅变更通知"
				description="向用户发送订阅级别、有效期等变更通知。"
				let:labelId
			>
				<Switch bind:state={settings.subscription_notifications} ariaLabelledbyId={labelId} />
			</AdminSettingRow>
		</AdminSettingSection>

		<AdminSettingSection title="测试">
			<AdminSettingField
				label="测试收件邮箱"
				description="发送一封测试邮件，检查模板和 SMTP 配置。"
			>
				<div class="flex w-full max-w-xl items-center gap-2">
					<input
						type="email"
						class={inputClass}
						placeholder="name@example.com"
						bind:value={testRecipient}
					/>
					<button
						type="button"
						class={actionButtonClass}
						disabled={sendingTest || saving}
						on:click={sendTest}
					>
						{sendingTest ? '发送中...' : '发送测试邮件'}
					</button>
				</div>
			</AdminSettingField>
		</AdminSettingSection>

		<div class="mt-5 flex justify-end">
			<button
				type="button"
				class={primaryButtonClass}
				disabled={saving || testingConnection || sendingTest}
				on:click={() => persist()}
			>
				{saving ? '保存中...' : '保存设置'}
			</button>
		</div>
	</div>
{/if}
