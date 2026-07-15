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
	import EmailCodeModal from '$lib/components/common/EmailCodeModal.svelte';
	import { emailErrorMessage } from '$lib/utils/email-errors';

	let show = false;
	let newEmail = '';
	let step: 'idle' | 'current' | 'new' = 'idle';
	let verificationModalOpen = false;
	let verificationChallengeStartedAt = 0;
	let busy = false;

	const finish = async (verificationToken: string | null) => {
		const updated = await updateUserEmail(
			localStorage.token,
			newEmail.trim().toLowerCase(),
			verificationToken
		).catch((error) => {
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
		if (step !== 'idle') {
			verificationModalOpen = true;
			return;
		}
		busy = true;
		try {
			const request = await requestSensitiveChallenge(localStorage.token, 'email').catch(
				(error) => {
					toast.error(emailErrorMessage(error));
					return null;
				}
			);
			if (request?.verification_required) {
				step = 'current';
				verificationChallengeStartedAt = Date.now();
				verificationModalOpen = true;
				toast.success('验证码已发送到当前登录邮箱');
			} else if (request?.status) {
				await finish(null);
			}
		} finally {
			busy = false;
		}
	};

	const restartVerification = () => {
		step = 'idle';
		verificationModalOpen = false;
		verificationChallengeStartedAt = 0;
	};

	const completeVerification = async (event: CustomEvent<{ code: string }>) => {
		busy = true;
		try {
			if (step === 'current') {
				const verified = await verifySensitiveChallenge(
					localStorage.token,
					'email',
					event.detail.code
				).catch((error) => {
					toast.error(emailErrorMessage(error));
					return null;
				});
				if (!verified?.verification_token) return;

				const request = await requestNewEmailChallenge(
					localStorage.token,
					newEmail.trim().toLowerCase(),
					verified.verification_token
				).catch((error) => {
					toast.error(emailErrorMessage(error));
					return null;
				});
				if (request?.verification_required) {
					step = 'new';
					verificationChallengeStartedAt = Date.now();
					toast.success('验证码已发送到新邮箱');
				} else if (request?.status) {
					verificationModalOpen = false;
					await finish(null);
				}
			} else if (step === 'new') {
				const verified = await verifyNewEmailChallenge(
					localStorage.token,
					newEmail.trim().toLowerCase(),
					event.detail.code
				).catch((error) => {
					toast.error(emailErrorMessage(error));
					return null;
				});
				if (verified?.verification_token) {
					verificationModalOpen = false;
					await finish(verified.verification_token);
				}
			}
		} finally {
			busy = false;
		}
	};

	const resendVerification = async () => {
		busy = true;
		try {
			if (step === 'new') {
				restartVerification();
				await submit();
				return;
			}
			const request = await requestSensitiveChallenge(localStorage.token, 'email').catch(
				(error) => {
					toast.error(emailErrorMessage(error));
					return null;
				}
			);
			if (request?.status) {
				verificationChallengeStartedAt = Date.now();
				toast.success('验证码已重新发送');
			}
		} finally {
			busy = false;
		}
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
			<input
				type="email"
				bind:value={newEmail}
				required
				class="bg-transparent outline-hidden"
				aria-label="新登录邮箱"
				placeholder="新登录邮箱"
			/>
			{#if step !== 'idle'}
				<button
					type="button"
					class="self-start text-xs font-medium text-gray-500 underline"
					on:click={restartVerification}>重新开始验证</button
				>
			{/if}
			<div>
				<button
					disabled={busy}
					class="rounded-full bg-black px-3 py-1.5 text-white disabled:opacity-50 dark:bg-white dark:text-black"
				>
					{step === 'idle' ? '验证并更改' : '继续验证'}
				</button>
			</div>
		</form>
	{/if}
</div>

<EmailCodeModal
	bind:show={verificationModalOpen}
	title={step === 'new' ? '验证新登录邮箱' : '验证当前邮箱'}
	description="请输入发送到以下邮箱的 6 位验证码"
	email={step === 'new' ? newEmail : ($user?.email ?? '')}
	confirmLabel={step === 'new' ? '验证新邮箱并更改' : '验证当前邮箱'}
	{busy}
	challengeStartedAt={verificationChallengeStartedAt}
	resendLabel={step === 'new' ? '重新开始验证' : '重新发送'}
	on:confirm={completeVerification}
	on:resend={resendVerification}
/>
