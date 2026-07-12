<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { resetPassword } from '$lib/apis/emails';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import ThemeLogo from '$lib/components/common/ThemeLogo.svelte';
	import { WEBUI_NAME } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { emailErrorMessage } from '$lib/utils/email-errors';

	let password = '';
	let confirmation = '';
	let submitting = false;
	let complete = false;
	$: token = $page.url.searchParams.get('token') ?? '';

	const submit = async () => {
		if (password !== confirmation) {
			toast.error('两次输入的密码不一致');
			return;
		}
		if (!token) {
			toast.error('重置链接无效');
			return;
		}
		submitting = true;
		const result = await resetPassword(token, password).catch((error) => {
			toast.error(emailErrorMessage(error));
			return null;
		});
		submitting = false;
		if (result?.status) complete = true;
	};
</script>

<svelte:head><title>重置密码 - {$WEBUI_NAME}</title></svelte:head>

<main class="min-h-[100dvh] bg-white px-6 text-gray-950 dark:bg-black dark:text-gray-100">
	<div class="mx-auto flex min-h-[100dvh] w-full max-w-sm flex-col justify-center py-12">
		<div class="mb-8 flex justify-center">
			<ThemeLogo kind="mark" className="size-16 rounded-full" alt="{$WEBUI_NAME} logo" />
		</div>
		<h1 class="text-center text-2xl font-semibold">重置密码</h1>

		{#if complete}
			<p class="mt-4 text-center text-sm text-gray-600 dark:text-gray-400">密码已重置，请使用新密码登录。</p>
			<button
				type="button"
				class="mt-6 w-full rounded-full bg-black px-4 py-2.5 text-sm font-medium text-white dark:bg-white dark:text-black"
				on:click={() => goto('/auth')}
			>
				前往登录
			</button>
		{:else if !token}
			<p class="mt-4 text-center text-sm text-red-600">重置链接无效或缺少令牌。</p>
			<button type="button" class="mt-6 text-sm font-medium underline" on:click={() => goto('/auth/forgot-password')}>
				重新获取链接
			</button>
		{:else}
			<form class="mt-6 space-y-4" on:submit|preventDefault={submit}>
				<div>
					<label for="new-password" class="mb-1 block text-sm font-medium">新密码</label>
					<SensitiveInput id="new-password" type="password" bind:value={password} autocomplete="new-password" required class="w-full border-b border-gray-300 bg-transparent py-2 text-sm outline-none dark:border-gray-700" />
				</div>
				<div>
					<label for="confirm-password" class="mb-1 block text-sm font-medium">确认新密码</label>
					<SensitiveInput id="confirm-password" type="password" bind:value={confirmation} autocomplete="new-password" required class="w-full border-b border-gray-300 bg-transparent py-2 text-sm outline-none dark:border-gray-700" />
				</div>
				<button
					type="submit"
					disabled={submitting}
					class="w-full rounded-full bg-black px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
				>
					{submitting ? '正在重置…' : '重置密码'}
				</button>
			</form>
		{/if}
	</div>
</main>
