<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { requestSensitiveChallenge, verifySensitiveChallenge } from '$lib/apis/emails';
	import { getMySubscription, updateBillingAddress } from '$lib/apis/subscriptions';

	let billingAddress = { name: '', country: '', address: '', postal_code: '', tax_id_or_notes: '' };
	let verificationCode = '';
	let verificationRequested = false;
	let busy = false;

	const load = async () => {
		const subscription = await getMySubscription(localStorage.token).catch(() => null);
		billingAddress = Object.assign({}, billingAddress, subscription?.billing_address ?? {});
	};

	const persist = async (verificationToken: string | null) => {
		await updateBillingAddress(localStorage.token, billingAddress, verificationToken)
			.then(() => {
				toast.success('付款信息已保存');
				verificationRequested = false;
				verificationCode = '';
			})
			.catch((error) => toast.error(`${error}`));
	};

	const save = async () => {
		busy = true;
		if (!verificationRequested) {
			const request = await requestSensitiveChallenge(localStorage.token, 'billing_address').catch((error) => {
				toast.error(`${error}`);
				return null;
			});
			if (request?.verification_required) {
				verificationRequested = true;
				toast.success('验证码已发送到当前登录邮箱');
			} else if (request?.status) {
				await persist(null);
			}
		} else {
			const verified = await verifySensitiveChallenge(localStorage.token, 'billing_address', verificationCode).catch(
				(error) => {
					toast.error(`${error}`);
					return null;
				}
			);
			if (verified?.verification_token) await persist(verified.verification_token);
		}
		busy = false;
	};

	onMount(load);
</script>

<div class="mt-4">
	<div class="mb-2 text-sm font-medium">付款信息</div>
	<div class="flex flex-col gap-2 text-sm">
		<input class="bg-transparent outline-hidden" aria-label="姓名或公司" placeholder="姓名或公司" bind:value={billingAddress.name} />
		<input class="bg-transparent outline-hidden" aria-label="国家或地区" placeholder="国家或地区" bind:value={billingAddress.country} />
		<input class="bg-transparent outline-hidden" aria-label="地址" placeholder="地址" bind:value={billingAddress.address} />
		<input class="bg-transparent outline-hidden" aria-label="邮政编码" placeholder="邮政编码" bind:value={billingAddress.postal_code} />
		<input class="bg-transparent outline-hidden" aria-label="税号或备注" placeholder="税号或备注" bind:value={billingAddress.tax_id_or_notes} />
		{#if verificationRequested}
			<input bind:value={verificationCode} inputmode="numeric" maxlength="6" pattern="[0-9]{6}" required class="bg-transparent outline-hidden" aria-label="邮箱验证码" placeholder="邮箱验证码" />
		{/if}
		<div>
			<button type="button" disabled={busy} class="rounded-full bg-black px-3 py-1.5 text-white disabled:opacity-50 dark:bg-white dark:text-black" on:click={save}>
				{verificationRequested ? '验证并保存' : '保存付款信息'}
			</button>
		</div>
	</div>
</div>
