<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Switch from '$lib/components/common/Switch.svelte';
	import {
		getRegistrationSettings,
		updateRegistrationSettings,
		type RegistrationSettings
	} from '$lib/apis/emails';

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

<div class="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-4 sm:px-6">
	<div class="border-b border-gray-100 pb-3 dark:border-gray-850">
		<h1 class="text-xl font-medium">注册管理</h1>
	</div>
	{#if loading}
		<div class="py-8 text-sm text-gray-500">加载中...</div>
	{:else}
		<label class="flex flex-col gap-1">
			<span class="text-xs text-gray-500">允许注册的邮箱后缀</span>
			<textarea
				rows="7"
				class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 font-mono text-sm dark:border-gray-850"
				placeholder="example.com"
				bind:value={domains}
			></textarea>
		</label>
		<div
			class="divide-y divide-gray-100 border-y border-gray-100 dark:divide-gray-850 dark:border-gray-850"
		>
			<label class="flex items-center justify-between gap-4 py-4"
				><span class="text-sm">允许子域名</span><Switch
					bind:state={settings.allow_subdomains}
					ariaLabel="允许子域名注册"
				/></label
			>
			<label class="flex items-center justify-between gap-4 py-4"
				><span class="text-sm">注册邮箱验证</span><Switch
					bind:state={settings.verification_enabled}
					ariaLabel="启用注册邮箱验证"
				/></label
			>
			<label class="flex items-center justify-between gap-4 py-4"
				><span class="text-sm">邮箱验证码登录</span><Switch
					bind:state={settings.email_code_login_enabled}
					ariaLabel="启用邮箱验证码登录"
				/></label
			>
			<label class="flex items-center justify-between gap-4 py-4"
				><span class="text-sm">敏感操作邮箱验证</span><Switch
					bind:state={settings.sensitive_action_verification_enabled}
					ariaLabel="启用敏感操作邮箱验证"
				/></label
			>
		</div>
		<div class="flex justify-end">
			<button
				type="button"
				class="rounded-lg bg-black px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-black"
				disabled={saving}
				on:click={save}>{saving ? '保存中...' : '保存设置'}</button
			>
		</div>
	{/if}
</div>
