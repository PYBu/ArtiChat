<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Switch from '$lib/components/common/Switch.svelte';
	import {
		getEmailSettings,
		sendEmailTest,
		testEmailConnection,
		updateEmailSettings,
		type EmailSettings
	} from '$lib/apis/emails';

	const defaults: EmailSettings = {
		enabled: false,
		host: '',
		port: 587,
		username: '',
		password: '',
		password_configured: false,
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
		SMTP_SEND_FAILED: '邮件发送失败，请检查发件人权限和收件地址。'
	};

	let settings = { ...defaults };
	let loading = true;
	let saving = false;
	let testingConnection = false;
	let sendingTest = false;
	let testRecipient = '';

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
		const { password_configured: _passwordConfigured, ...payload } = settings;
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
	<div class="flex max-w-4xl flex-col gap-6">
		<section class="flex flex-col gap-4 border-b border-gray-100 pb-6 dark:border-gray-850">
			<div class="flex items-center justify-between gap-4">
				<div class="font-medium">发信服务</div>
				<Switch bind:state={settings.enabled} ariaLabel="启用发信服务" />
			</div>
			<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
				<label class="flex flex-col gap-1 sm:col-span-2">
					<span class="text-xs text-gray-500">SMTP 主机</span>
					<input
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.host}
						autocomplete="off"
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">端口</span>
					<input
						type="number"
						min="1"
						max="65535"
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.port}
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">安全模式</span>
					<select
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.security}
					>
						<option value="starttls">STARTTLS</option>
						<option value="ssl">SSL/TLS</option>
						<option value="none">无加密</option>
					</select>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">用户名</span>
					<input
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.username}
						autocomplete="username"
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">密码</span>
					<input
						type="password"
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.password}
						autocomplete="new-password"
					/>
				</label>
			</div>
		</section>

		<section class="flex flex-col gap-4 border-b border-gray-100 pb-6 dark:border-gray-850">
			<div class="font-medium">发件信息</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<label class="flex flex-col gap-1"
					><span class="text-xs text-gray-500">发件人地址</span><input
						type="email"
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.sender_email}
					/></label
				>
				<label class="flex flex-col gap-1"
					><span class="text-xs text-gray-500">发件人名称</span><input
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.sender_name}
					/></label
				>
				<label class="flex flex-col gap-1"
					><span class="text-xs text-gray-500">Reply-To</span><input
						type="email"
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.reply_to}
					/></label
				>
				<label class="flex flex-col gap-1"
					><span class="text-xs text-gray-500">平台访问地址</span><input
						type="url"
						class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
						bind:value={settings.public_url}
					/></label
				>
			</div>
			<div class="flex items-center justify-between gap-4">
				<span class="text-sm">订阅变更通知</span>
				<Switch bind:state={settings.subscription_notifications} ariaLabel="发送订阅变更通知" />
			</div>
		</section>

		<section class="flex flex-col gap-4">
			<div class="font-medium">测试</div>
			<div class="flex flex-col gap-3 sm:flex-row">
				<input
					type="email"
					class="min-w-0 flex-1 rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
					placeholder="测试收件邮箱"
					bind:value={testRecipient}
				/>
				<button
					type="button"
					class="rounded-lg border border-gray-200 px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50 dark:border-gray-800 dark:hover:bg-gray-900"
					disabled={sendingTest || saving}
					on:click={sendTest}>{sendingTest ? '发送中...' : '发送测试邮件'}</button
				>
			</div>
			<div class="flex flex-wrap justify-end gap-2">
				<button
					type="button"
					class="rounded-lg border border-gray-200 px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50 dark:border-gray-800 dark:hover:bg-gray-900"
					disabled={testingConnection || saving}
					on:click={checkConnection}>{testingConnection ? '测试中...' : '保存并测试连接'}</button
				>
				<button
					type="button"
					class="rounded-lg bg-black px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-black"
					disabled={saving || testingConnection || sendingTest}
					on:click={() => persist()}>{saving ? '保存中...' : '保存设置'}</button
				>
			</div>
		</section>
	</div>
{/if}
