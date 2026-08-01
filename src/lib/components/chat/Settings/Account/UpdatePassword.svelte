<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { updateUserPasswordWithVerification } from '$lib/apis/account-security';
	import { requestSensitiveChallenge, verifySensitiveChallenge } from '$lib/apis/emails';
	import { user } from '$lib/stores';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import EmailCodeModal from '$lib/components/common/EmailCodeModal.svelte';
	import { emailErrorMessage } from '$lib/utils/email-errors';

	const i18n: Writable<any> = getContext('i18n');

	let show = false;
	let currentPassword = '';
	let newPassword = '';
	let newPasswordConfirm = '';
	let verificationModalOpen = false;
	let verificationChallengeStartedAt = 0;
	let busy = false;
	const actionButtonClass =
		'text-xs text-gray-500 transition-colors hover:text-gray-900 dark:text-gray-500 dark:hover:text-white';

	const persist = async (verificationToken: string | null) => {
		const result = await updateUserPasswordWithVerification(
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
				toast.success($i18n.t('A verification code was sent to your email.'));
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
			toast.success($i18n.t('A new verification code was sent.'));
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

<form
	class="flex flex-col text-sm"
	on:submit|preventDefault={() => {
		updatePasswordHandler();
	}}
>
	<div class="flex items-center justify-between gap-2.5">
		<div class="text-xs text-gray-600 dark:text-gray-400">{$i18n.t('Change Password')}</div>
		<button
			class={actionButtonClass}
			type="button"
			on:click={() => {
				show = !show;
			}}>{show ? $i18n.t('Hide') : $i18n.t('Show')}</button
		>
	</div>
	<p class="mt-0.5 text-[0.6875rem] text-gray-400 dark:text-gray-600">
		{$i18n.t('Update the password used for email and password sign-in.')}
	</p>

	{#if show}
		<div class="py-2.5 space-y-2.5">
			<div class="flex flex-col w-full">
				<div class="mb-1 text-xs text-gray-600 dark:text-gray-400">
					{$i18n.t('Current Password')}
				</div>

				<div class="flex-1">
					<SensitiveInput
						variant="settings"
						type="password"
						bind:value={currentPassword}
						placeholder={$i18n.t('Enter your current password')}
						autocomplete="current-password"
						required
					/>
				</div>
			</div>

			<div class="flex flex-col w-full">
				<div class="mb-1 text-xs text-gray-600 dark:text-gray-400">
					{$i18n.t('New Password')}
				</div>

				<div class="flex-1">
					<SensitiveInput
						variant="settings"
						type="password"
						bind:value={newPassword}
						placeholder={$i18n.t('Enter your new password')}
						autocomplete="new-password"
						required
					/>
				</div>
			</div>

			<div class="flex flex-col w-full">
				<div class="mb-1 text-xs text-gray-600 dark:text-gray-400">
					{$i18n.t('Confirm Password')}
				</div>

				<div class="flex-1">
					<SensitiveInput
						variant="settings"
						type="password"
						bind:value={newPasswordConfirm}
						placeholder={$i18n.t('Confirm your new password')}
						autocomplete="off"
						required
					/>
				</div>
			</div>
		</div>

		<div class="flex justify-end">
			<button class={actionButtonClass} disabled={busy}>
				{$i18n.t('Update password')}
			</button>
		</div>
	{/if}
</form>

<EmailCodeModal
	bind:show={verificationModalOpen}
	title={$i18n.t('Verify your email to change your password')}
	description={$i18n.t('Enter the six-digit code sent to your account email.')}
	email={$user?.email ?? ''}
	confirmLabel={$i18n.t('Verify and update password')}
	{busy}
	challengeStartedAt={verificationChallengeStartedAt}
	on:confirm={completeVerification}
	on:resend={resendVerification}
/>
