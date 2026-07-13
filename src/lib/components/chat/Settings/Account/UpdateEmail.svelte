<script lang="ts">
	import { goto } from '$app/navigation';
	import { updateUserEmail } from '$lib/apis/auths';
	import {
		requestNewEmailChallenge,
		requestSensitiveChallenge,
		verifyNewEmailChallenge,
		verifySensitiveChallenge
	} from '$lib/apis/emails';
	import { user } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { emailErrorMessage } from '$lib/utils/email-errors';

	let show = false;
	let newEmail = '';
	let currentCode = '';
	let newCode = '';
	let step: 'idle' | 'current' | 'new' = 'idle';
	let busy = false;

	const finish = async (verificationToken: string | null) => {
		const updated = await updateUserEmail(localStorage.token, newEmail, verificationToken).catch((error) => {
			toast.error(emailErrorMessage(error));
			return false;
		});
		if (updated) {
			localStorage.removeItem('token');
			await user.set(undefined);
			toast.success('登录邮箱已更新，请重新登录');
			await goto('/auth');
		}
	};

	const submit = async () => {
		busy = true;
		if (step === 'idle') {
			const request = await requestSensitiveChallenge(localStorage.token, 'email').catch((error) => {
				toast.error(emailErrorMessage(error));
				return null;
			});
			if (request?.verification_required) {
				step = 'current';
				toast.success('验证码已发送到当前登录邮箱');
			} else if (request?.status) {
				await finish(null);
			}
		} else if (step === 'current') {
			const verified = await verifySensitiveChallenge(localStorage.token, 'email', currentCode).catch((error) => {
				toast.error(emailErrorMessage(error));
				return null;
			});
			if (verified?.verification_token) {
				const request = await requestNewEmailChallenge(
					localStorage.token,
					newEmail,
					verified.verification_token
				).catch((error) => {
					toast.error(emailErrorMessage(error));
					return null;
				});
				if (request?.verification_required) {
					step = 'new';
					toast.success('验证码已发送到新邮箱');
				} else if (request?.status) {
					await finish(null);
				}
			}
		} else {
			const verified = await verifyNewEmailChallenge(localStorage.token, newEmail, newCode).catch((error) => {
				toast.error(emailErrorMessage(error));
				return null;
			});
			if (verified?.verification_token) await finish(verified.verification_token);
		}
		busy = false;
	};

	const restartVerification = () => {
		step = 'idle';
		currentCode = '';
		newCode = '';
	};
</script>

<div class="mt-4 text-sm">
	<div class="flex items-center justify-between">
		<div>
			<div class="font-medium">登录邮箱</div>
			<div class="mt-0.5 text-xs text-gray-500">{$user?.email}</div>
		</div>
		<button type="button" class="text-xs font-medium text-gray-500" on:click={() => (show = !show)}>
			{show ? '收起' : '更改'}
		</button>
	</div>
	{#if show}
		<form class="mt-3 flex flex-col gap-2" on:submit|preventDefault={submit}>
			<input type="email" bind:value={newEmail} required class="bg-transparent outline-hidden" aria-label="新登录邮箱" placeholder="新登录邮箱" />
			{#if step === 'current'}
				<input bind:value={currentCode} inputmode="numeric" maxlength="6" pattern="[0-9]{6}" required class="bg-transparent outline-hidden" aria-label="当前邮箱验证码" placeholder="当前邮箱验证码" />
			{:else if step === 'new'}
				<input bind:value={newCode} inputmode="numeric" maxlength="6" pattern="[0-9]{6}" required class="bg-transparent outline-hidden" aria-label="新邮箱验证码" placeholder="新邮箱验证码" />
			{/if}
			{#if step !== 'idle'}
				<button type="button" class="self-start text-xs font-medium text-gray-500 underline" on:click={restartVerification}>重新开始验证</button>
			{/if}
			<div>
				<button disabled={busy} class="rounded-full bg-black px-3 py-1.5 text-white disabled:opacity-50 dark:bg-white dark:text-black">
					{step === 'idle' ? '验证并更改' : step === 'current' ? '验证当前邮箱' : '验证新邮箱并更改'}
				</button>
			</div>
		</form>
	{/if}
</div>
