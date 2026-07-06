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
			.then(() => toast.success('Billing address saved.'))
			.catch((error) => toast.error(`${error}`));
	};

	onMount(load);
</script>

<div class="mt-4">
	<div class="mb-2 text-sm font-medium">Billing Address</div>
	<div class="flex flex-col gap-2 text-sm">
		<input class="bg-transparent outline-hidden" aria-label="Name or company" bind:value={billingAddress.name} />
		<input class="bg-transparent outline-hidden" aria-label="Country / region" bind:value={billingAddress.country} />
		<input class="bg-transparent outline-hidden" aria-label="Address" bind:value={billingAddress.address} />
		<input class="bg-transparent outline-hidden" aria-label="Postal code" bind:value={billingAddress.postal_code} />
		<input class="bg-transparent outline-hidden" aria-label="Tax ID or notes" bind:value={billingAddress.tax_id_or_notes} />
		<div>
			<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" on:click={save}>
				Save Billing Address
			</button>
		</div>
	</div>
</div>
