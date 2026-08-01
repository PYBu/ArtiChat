<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import AdminSettingField from '$lib/components/admin/Settings/AdminSettingField.svelte';
	import AdminSettingRow from '$lib/components/admin/Settings/AdminSettingRow.svelte';
	import AdminSettingSection from '$lib/components/admin/Settings/AdminSettingSection.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import {
		getRegistrationSettings,
		updateRegistrationSettings,
		type RegistrationSettings
	} from '$lib/apis/emails';

	export let embedded = false;
	export let emailEnabled = true;

	let settings: RegistrationSettings = {
		allowed_domains: [],
		allow_subdomains: false,
		verification_enabled: false,
		email_code_login_enabled: false,
		sensitive_action_verification_enabled: false
	};
	let domains = '';
	let loading = true;
	let saving = false;

	const textareaClass =
		'w-full max-w-xl rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 font-mono text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';

	const load = async () => {
		loading = true;
		settings = await getRegistrationSettings(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return settings;
		});
		domains = settings.allowed_domains.join('\n');
		loading = false;
	};

	const save = async () => {
		saving = true;
		const saved = await updateRegistrationSettings(localStorage.token, {
			...settings,
			allowed_domains: domains
				.split(/[\n,]/)
				.map((item) => item.trim())
				.filter(Boolean)
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (saved) {
			settings = saved;
			domains = saved.allowed_domains.join('\n');
			toast.success('注册设置已保存。');
		}
		saving = false;
	};

	onMount(load);
</script>

<div
	class={embedded
		? 'flex w-full flex-col'
		: 'mx-auto flex w-full max-w-4xl flex-col px-4 py-4 sm:px-6'}
>
	{#if !embedded}
		<h2 class="mb-4 text-sm font-medium text-gray-900 dark:text-white">注册管理</h2>
	{/if}

	{#if loading}
		<div class="py-8 text-sm text-gray-500">加载中...</div>
	{:else}
		<AdminSettingSection title="注册范围" first={!embedded}>
			<AdminSettingField
				label="允许注册的邮箱后缀"
				description="每行填写一个域名；留空表示不限制域名。"
			>
				<textarea rows="7" class={textareaClass} placeholder="example.com" bind:value={domains}
				></textarea>
			</AdminSettingField>
		</AdminSettingSection>

		<AdminSettingSection title="验证与登录">
			<AdminSettingRow label="允许子域名" description="同时允许配置域名的子域名注册。" let:labelId>
				<Switch bind:state={settings.allow_subdomains} ariaLabelledbyId={labelId} />
			</AdminSettingRow>
			{#if emailEnabled}
				<AdminSettingRow
					label="注册邮箱验证"
					description="注册时要求用户验证邮箱地址。"
					let:labelId
				>
					<Switch bind:state={settings.verification_enabled} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				<AdminSettingRow
					label="邮箱验证码登录"
					description="允许用户使用一次性邮箱验证码登录。"
					let:labelId
				>
					<Switch bind:state={settings.email_code_login_enabled} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				<AdminSettingRow
					label="敏感操作邮箱验证"
					description="修改密码、邮箱和付款信息时要求邮箱验证码。"
					let:labelId
				>
					<Switch
						bind:state={settings.sensitive_action_verification_enabled}
						ariaLabelledbyId={labelId}
					/>
				</AdminSettingRow>
			{:else}
				<div class="py-2 text-xs text-gray-500">
					启用邮箱功能后可配置注册验证、验证码登录和敏感操作验证。
				</div>
			{/if}
		</AdminSettingSection>

		<div class="mt-5 flex justify-end">
			<button
				type="button"
				class="h-7 rounded-lg bg-black px-3 text-xs font-medium text-white transition hover:bg-gray-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-gray-200"
				disabled={saving}
				on:click={save}>{saving ? '保存中...' : '保存设置'}</button
			>
		</div>
	{/if}
</div>
