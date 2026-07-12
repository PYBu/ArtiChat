<script lang="ts">
	import { goto } from '$app/navigation';
	import { forgotPassword } from '$lib/apis/emails';
	import ThemeLogo from '$lib/components/common/ThemeLogo.svelte';
	import { WEBUI_NAME } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { emailErrorMessage } from '$lib/utils/email-errors';

	let email = '';
	let sending = false;
	let sent = false;

	const submit = async () => {
		sending = true;
		const result = await forgotPassword(email).catch((error) => {
			toast.error(emailErrorMessage(error));
			return null;
		});
		sending = false;
		if (result?.status) sent = true;
	};
</script>

<svelte:head><title>找回密码 - {$WEBUI_NAME}</title></svelte:head>

<main class="min-h-[100dvh] bg-white px-6 text-gray-950 dark:bg-black dark:text-gray-100">
	<div class="mx-auto flex min-h-[100dvh] w-full max-w-sm flex-col justify-center py-12">
		<div class="mb-8 flex justify-center">
			<ThemeLogo kind="mark" className="size-16 rounded-full" alt="{$WEBUI_NAME} logo" />
		</div>
		<h1 class="text-center text-2xl font-semibold">找回密码</h1>

		{#if sent}
			<p class="mt-4 text-center text-sm leading-6 text-gray-600 dark:text-gray-400">
				如果该邮箱已注册并且邮件服务可用，你会收到一封密码重置邮件。链接 30 分钟内有效。
			</p>
			<button
				type="button"
				class="mt-6 w-full rounded-full bg-black px-4 py-2.5 text-sm font-medium text-white dark:bg-white dark:text-black"
				on:click={() => goto('/auth')}
			>
				返回登录
			</button>
		{:else}
			<form class="mt-6" on:submit|preventDefault={submit}>
				<label for="reset-email" class="mb-1 block text-sm font-medium">邮箱</label>
				<input
					id="reset-email"
					type="email"
					bind:value={email}
					autocomplete="email"
					required
					class="w-full border-b border-gray-300 bg-transparent py-2 text-sm outline-none focus:border-gray-900 dark:border-gray-700 dark:focus:border-gray-100"
					placeholder="name@example.com"
				/>
				<button
					type="submit"
					disabled={sending}
					class="mt-6 w-full rounded-full bg-black px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
				>
					{sending ? '正在发送…' : '发送重置邮件'}
				</button>
			</form>
			<button
				type="button"
				class="mt-4 w-full text-center text-sm font-medium text-gray-500 hover:text-gray-900 dark:hover:text-gray-100"
				on:click={() => goto('/auth')}
			>
				返回登录
			</button>
		{/if}
	</div>
</main>
