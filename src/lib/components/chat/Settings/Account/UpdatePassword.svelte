<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { updateUserPassword } from '$lib/apis/auths';
	import { requestSensitiveChallenge, verifySensitiveChallenge } from '$lib/apis/emails';
	import { user } from '$lib/stores';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import EmailCodeModal from '$lib/components/common/EmailCodeModal.svelte';
	import { emailErrorMessage } from '$lib/utils/email-errors';

	const i18n = getContext('i18n');
	let show = false;
	let currentPassword = '';
	let newPassword = '';
	let newPasswordConfirm = '';
	let verificationModalOpen = false;
	let verificationChallengeStartedAt = 0;
	let busy = false;

	const persist = async (verificationToken: string | null) => {
		const result = await updateUserPassword(
			localStorage.token,
			currentPassword,
			newPassword,
			verificationToken
		).catch((error) => {
			toast.error(emailErrorMessage(error));
			return null;
		});
		if (result) {
			toast.success($i18n.t('Successfully updated.'));
			currentPassword = '';
			newPassword = '';
			newPasswordConfirm = '';
			verificationModalOpen = false;
			verificationChallengeStartedAt = 0;
		}
		return result;
	};

	const updatePasswordHandler = async () => {
		if (newPassword !== newPasswordConfirm) {
			toast.error(
				$i18n.t("The passwords you entered don't quite match. Please double-check and try again.")
			);
			newPassword = '';
			newPasswordConfirm = '';
			return;
		}
		if (verificationChallengeStartedAt + 10 * 60 * 1000 > Date.now()) {
			verificationModalOpen = true;
			return;
		}
		busy = true;
		try {
			const request = await requestSensitiveChallenge(localStorage.token, 'password').catch(
				(error) => {
					toast.error(emailErrorMessage(error));
					return null;
				}
			);
			if (request?.verification_required) {
				verificationChallengeStartedAt = Date.now();
				verificationModalOpen = true;
				toast.success('验证码已发送到当前登录邮箱');
			} else if (request?.status) {
				await persist(null);
			}
		} finally {
			busy = false;
		}
	};

	const resendVerification = async () => {
		busy = true;
		const result = await requestSensitiveChallenge(localStorage.token, 'password').catch(
			(error) => {
				toast.error(emailErrorMessage(error));
				return null;
			}
		);
		if (result?.status) {
			verificationChallengeStartedAt = Date.now();
			toast.success('验证码已重新发送');
		}
		busy = false;
	};

	const completeVerification = async (event: CustomEvent<{ code: string }>) => {
		busy = true;
		const verified = await verifySensitiveChallenge(
			localStorage.token,
			'password',
			event.detail.code
		).catch((error) => {
			toast.error(emailErrorMessage(error));
			return null;
		});
		if (verified?.verification_token) await persist(verified.verification_token);
		busy = false;
	};
</script>

<form class="flex flex-col text-sm" on:submit|preventDefault={updatePasswordHandler}>
	<div class="flex items-center justify-between text-sm">
		<div class="font-medium">{$i18n.t('Change Password')}</div>
		<button class="text-xs font-medium text-gray-500" type="button" on:click={() => (show = !show)}>
			{show ? $i18n.t('Hide') : $i18n.t('Show')}
		</button>
	</div>

	{#if show}
		<div class="space-y-1.5 py-2.5">
			<div>
				<div class="mb-1 text-xs text-gray-500">{$i18n.t('Current Password')}</div>
				<SensitiveInput
					class="w-full bg-transparent text-sm outline-hidden dark:text-gray-300"
					type="password"
					bind:value={currentPassword}
					autocomplete="current-password"
					required
				/>
			</div>
			<div>
				<div class="mb-1 text-xs text-gray-500">{$i18n.t('New Password')}</div>
				<SensitiveInput
					class="w-full bg-transparent text-sm outline-hidden dark:text-gray-300"
					type="password"
					bind:value={newPassword}
					autocomplete="new-password"
					required
				/>
			</div>
			<div>
				<div class="mb-1 text-xs text-gray-500">{$i18n.t('Confirm Password')}</div>
				<SensitiveInput
					class="w-full bg-transparent text-sm outline-hidden dark:text-gray-300"
					type="password"
					bind:value={newPasswordConfirm}
					autocomplete="new-password"
					required
				/>
			</div>
		</div>
		<div class="mt-3 flex justify-end">
			<button
				disabled={busy}
				class="rounded-full bg-black px-3.5 py-1.5 text-sm font-medium text-white transition disabled:opacity-50 dark:bg-white dark:text-black"
			>
				{$i18n.t('Update password')}
			</button>
		</div>
	{/if}
</form>

<EmailCodeModal
	bind:show={verificationModalOpen}
	title="验证邮箱并修改密码"
	description="请输入发送到以下邮箱的 6 位验证码"
	email={$user?.email ?? ''}
	confirmLabel="验证并更新密码"
	{busy}
	challengeStartedAt={verificationChallengeStartedAt}
	on:confirm={completeVerification}
	on:resend={resendVerification}
/>
