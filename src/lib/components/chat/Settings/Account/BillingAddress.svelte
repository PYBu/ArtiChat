<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { requestSensitiveChallenge, verifySensitiveChallenge } from '$lib/apis/emails';
	import { getMySubscription, updateBillingAddress } from '$lib/apis/subscriptions';
	import { user } from '$lib/stores';
	import EmailCodeModal from '$lib/components/common/EmailCodeModal.svelte';
	import { emailErrorMessage } from '$lib/utils/email-errors';

	let billingAddress = { name: '', country: '', address: '', postal_code: '', tax_id_or_notes: '' };
	let verificationModalOpen = false;
	let verificationChallengeStartedAt = 0;
	let busy = false;

	const load = async () => {
		const subscription = await getMySubscription(localStorage.token).catch(() => null);
		billingAddress = Object.assign({}, billingAddress, subscription?.billing_address ?? {});
	};

	const persist = async (verificationToken: string | null) => {
		await updateBillingAddress(localStorage.token, billingAddress, verificationToken)
			.then(() => {
				toast.success('付款信息已保存');
				verificationModalOpen = false;
				verificationChallengeStartedAt = 0;
			})
			.catch((error) => toast.error(emailErrorMessage(error)));
	};

	const save = async () => {
		if (verificationChallengeStartedAt + 10 * 60 * 1000 > Date.now()) {
			verificationModalOpen = true;
			return;
		}
		busy = true;
		try {
			const request = await requestSensitiveChallenge(localStorage.token, 'billing_address').catch(
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
		const result = await requestSensitiveChallenge(localStorage.token, 'billing_address').catch(
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
			'billing_address',
			event.detail.code
		).catch((error) => {
			toast.error(emailErrorMessage(error));
			return null;
		});
		if (verified?.verification_token) await persist(verified.verification_token);
		busy = false;
	};

	onMount(load);
</script>

<section class="mt-4 rounded-lg border border-gray-100 p-3 dark:border-gray-850">
	<div class="flex items-start justify-between gap-3">
		<div>
			<div class="text-[13px] font-medium text-gray-900 dark:text-white">付款信息</div>
			<div class="mt-1 text-[0.6875rem] text-gray-500 dark:text-gray-400">
				用于付款记录、账单抬头和发票联系信息。
			</div>
		</div>
	</div>

	<div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
		<label class="min-w-0">
			<span class="mb-1 block text-[0.6875rem] text-gray-600 dark:text-gray-400"
				>姓名或公司名称</span
			>
			<input
				class="h-7 w-full rounded-lg border border-gray-200 bg-transparent px-2.5 text-xs outline-hidden transition focus:border-gray-400 dark:border-gray-800 dark:focus:border-gray-600"
				aria-label="姓名或公司"
				placeholder="姓名或公司"
				bind:value={billingAddress.name}
			/>
		</label>
		<label class="min-w-0">
			<span class="mb-1 block text-[0.6875rem] text-gray-600 dark:text-gray-400">国家或地区</span>
			<input
				class="h-7 w-full rounded-lg border border-gray-200 bg-transparent px-2.5 text-xs outline-hidden transition focus:border-gray-400 dark:border-gray-800 dark:focus:border-gray-600"
				aria-label="国家或地区"
				placeholder="国家或地区"
				bind:value={billingAddress.country}
			/>
		</label>
		<label class="min-w-0 sm:col-span-2">
			<span class="mb-1 block text-[0.6875rem] text-gray-600 dark:text-gray-400">地址</span>
			<input
				class="h-7 w-full rounded-lg border border-gray-200 bg-transparent px-2.5 text-xs outline-hidden transition focus:border-gray-400 dark:border-gray-800 dark:focus:border-gray-600"
				aria-label="地址"
				placeholder="地址"
				bind:value={billingAddress.address}
			/>
		</label>
		<label class="min-w-0">
			<span class="mb-1 block text-[0.6875rem] text-gray-600 dark:text-gray-400">邮政编码</span>
			<input
				class="h-7 w-full rounded-lg border border-gray-200 bg-transparent px-2.5 text-xs outline-hidden transition focus:border-gray-400 dark:border-gray-800 dark:focus:border-gray-600"
				aria-label="邮政编码"
				placeholder="邮政编码"
				bind:value={billingAddress.postal_code}
			/>
		</label>
		<label class="min-w-0">
			<span class="mb-1 block text-[0.6875rem] text-gray-600 dark:text-gray-400">税号或备注</span>
			<input
				class="h-7 w-full rounded-lg border border-gray-200 bg-transparent px-2.5 text-xs outline-hidden transition focus:border-gray-400 dark:border-gray-800 dark:focus:border-gray-600"
				aria-label="税号或备注"
				placeholder="税号或备注"
				bind:value={billingAddress.tax_id_or_notes}
			/>
		</label>
	</div>

	<div class="mt-3 flex justify-end">
		<button
			type="button"
			disabled={busy}
			class="h-7 rounded-lg bg-black px-3 text-xs font-medium text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-gray-200"
			on:click={save}
		>
			保存付款信息
		</button>
	</div>
</section>

<EmailCodeModal
	bind:show={verificationModalOpen}
	title="验证邮箱并保存付款信息"
	description="请输入发送到以下邮箱的 6 位验证码"
	email={$user?.email ?? ''}
	confirmLabel="验证并保存"
	{busy}
	challengeStartedAt={verificationChallengeStartedAt}
	on:confirm={completeVerification}
	on:resend={resendVerification}
/>
