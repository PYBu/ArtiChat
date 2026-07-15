<script lang="ts">
	import { createEventDispatcher, onDestroy, onMount, tick } from 'svelte';

	import XMark from '$lib/components/icons/XMark.svelte';
	import {
		isEmailVerificationCodeComplete,
		normalizeEmailVerificationCode
	} from '$lib/utils/email-verification';

	import Modal from './Modal.svelte';

	export let show = false;
	export let title = '邮箱验证';
	export let description = '请输入发送到以下邮箱的验证码';
	export let email = '';
	export let confirmLabel = '确认验证';
	export let busy = false;
	export let challengeStartedAt = 0;
	export let resendLabel = '重新发送';
	export let canResend = true;

	const dispatch = createEventDispatcher<{
		confirm: { code: string };
		resend: void;
	}>();

	let code = '';
	let validationError = '';
	let resendSeconds = 0;
	let expiresSeconds = 0;
	let activeChallengeStartedAt = 0;
	let wasShown = false;
	let inputElement: HTMLInputElement | null = null;
	let timer: number | undefined;

	const refreshCountdowns = () => {
		if (!challengeStartedAt) {
			resendSeconds = 0;
			expiresSeconds = 0;
			return;
		}

		const elapsedSeconds = Math.floor((Date.now() - challengeStartedAt) / 1000);
		resendSeconds = Math.max(0, 60 - elapsedSeconds);
		expiresSeconds = Math.max(0, 600 - elapsedSeconds);
	};

	const focusInput = async () => {
		await tick();
		inputElement?.focus();
	};

	$: if (show && challengeStartedAt !== activeChallengeStartedAt) {
		activeChallengeStartedAt = challengeStartedAt;
		code = '';
		validationError = '';
		refreshCountdowns();
		void focusInput();
	}

	$: if (show && !wasShown) {
		wasShown = true;
		refreshCountdowns();
		void focusInput();
	} else if (!show && wasShown) {
		wasShown = false;
	}

	const handleInput = (event: Event) => {
		code = normalizeEmailVerificationCode((event.currentTarget as HTMLInputElement).value);
		validationError = '';
	};

	const submit = () => {
		code = normalizeEmailVerificationCode(code);
		if (expiresSeconds <= 0) {
			validationError = '验证码已过期，请重新发送。';
			return;
		}
		if (!isEmailVerificationCodeComplete(code)) {
			validationError = '请输入 6 位数字验证码。';
			return;
		}
		dispatch('confirm', { code });
	};

	const resend = () => {
		if (!canResend || busy || resendSeconds > 0) return;
		code = '';
		validationError = '';
		dispatch('resend');
	};

	onMount(() => {
		refreshCountdowns();
		timer = window.setInterval(refreshCountdowns, 1000);
	});

	onDestroy(() => {
		if (timer !== undefined) window.clearInterval(timer);
	});
</script>

<Modal
	bind:show
	size="sm"
	className="rounded-lg bg-white dark:bg-gray-900"
	closeOnBackdrop={false}
	closeOnEscape={false}
>
	<form class="p-5 text-left text-gray-900 dark:text-gray-100" on:submit|preventDefault={submit}>
		<div class="flex items-start justify-between gap-4">
			<div class="min-w-0">
				<h2 class="text-lg font-semibold">{title}</h2>
				<p class="mt-1 text-sm leading-6 text-gray-500 dark:text-gray-400">{description}</p>
				{#if email}
					<p class="mt-1 break-all text-sm font-medium">{email}</p>
				{/if}
			</div>
			<button
				type="button"
				class="shrink-0 rounded-md p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
				aria-label="关闭验证码弹窗"
				on:click={() => (show = false)}
			>
				<XMark className="size-5" />
			</button>
		</div>

		<label class="mt-5 block">
			<span class="mb-1.5 block text-sm font-medium">邮箱验证码</span>
			<input
				bind:this={inputElement}
				bind:value={code}
				type="text"
				inputmode="numeric"
				autocomplete="one-time-code"
				class="h-11 w-full rounded-md border border-gray-200 bg-transparent px-3 text-center text-lg outline-hidden focus:border-gray-500 dark:border-gray-700 dark:focus:border-gray-400"
				aria-label="邮箱验证码"
				aria-invalid={validationError ? 'true' : 'false'}
				on:input={handleInput}
			/>
		</label>

		<div class="mt-2 min-h-5 text-xs">
			{#if validationError}
				<span class="text-red-600 dark:text-red-400">{validationError}</span>
			{:else}
				<span class="text-gray-500">
					{expiresSeconds > 0 ? `验证码将在 ${expiresSeconds} 秒后过期` : '验证码已过期'}
				</span>
			{/if}
		</div>

		<div class="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
			<button
				type="button"
				class="h-10 rounded-md px-3 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-50 dark:text-gray-300 dark:hover:bg-gray-800"
				disabled={!canResend || busy || resendSeconds > 0}
				on:click={resend}
			>
				{resendSeconds > 0 ? `${resendSeconds} 秒后可重发` : resendLabel}
			</button>
			<button
				type="submit"
				class="h-10 rounded-md bg-black px-4 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
				disabled={busy}
			>
				{busy ? '验证中...' : confirmLabel}
			</button>
		</div>
	</form>
</Modal>
