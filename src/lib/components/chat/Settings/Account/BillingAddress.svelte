<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getMySubscription, updateBillingAddress } from '$lib/apis/subscriptions';

	let billingAddress = {
		name: '',
		country: '',
		address: '',
		postal_code: '',
		tax_id_or_notes: ''
	};

	const load = async () => {
		const subscription = await getMySubscription(localStorage.token).catch(() => null);
		billingAddress = Object.assign({}, billingAddress, subscription?.billing_address ?? {});
	};

	const save = async () => {
		await updateBillingAddress(localStorage.token, billingAddress)
			.then(() => toast.success('账单地址已保存。'))
			.catch((error) => toast.error(`${error}`));
	};

	onMount(load);
</script>

<div class="mt-4">
	<div class="mb-2 text-sm font-medium">账单地址</div>
	<div class="flex flex-col gap-2 text-sm">
		<input class="bg-transparent outline-hidden" aria-label="姓名或公司" placeholder="姓名或公司" bind:value={billingAddress.name} />
		<input class="bg-transparent outline-hidden" aria-label="国家或地区" placeholder="国家或地区" bind:value={billingAddress.country} />
		<input class="bg-transparent outline-hidden" aria-label="地址" placeholder="地址" bind:value={billingAddress.address} />
		<input class="bg-transparent outline-hidden" aria-label="邮政编码" placeholder="邮政编码" bind:value={billingAddress.postal_code} />
		<input class="bg-transparent outline-hidden" aria-label="税号或备注" placeholder="税号或备注" bind:value={billingAddress.tax_id_or_notes} />
		<div>
			<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" on:click={save}>
				保存账单地址
			</button>
		</div>
	</div>
</div>
