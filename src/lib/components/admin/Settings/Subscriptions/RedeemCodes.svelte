<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { createAdminRedemptionCodes, getAdminRedemptionCodes } from '$lib/apis/subscriptions';

	let codes: any[] = [];
	let generatedCodes: string[] = [];
	let loading = true;
	let creating = false;

	let form = {
		mode: 'single_use',
		quantity: 1,
		max_uses: 1,
		tier: 'plus',
		duration_days: 30,
		plan_chatpoint: 100,
		check_chatpoint: 0,
		memo: ''
	};

	const formatChatpoint = (micros?: number | null) => ((micros ?? 0) / 1_000_000).toLocaleString();
	const formatDate = (value?: number | null) => (value ? new Date(value * 1000).toLocaleString() : '-');

	const load = async () => {
		loading = true;
		const response = await getAdminRedemptionCodes(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return { items: [] };
		});
		codes = response?.items ?? [];
		loading = false;
	};

	const createCodes = async () => {
		creating = true;
		generatedCodes = [];
		const payload = {
			...form,
			quantity: form.mode === 'multi_use' ? 1 : Number(form.quantity),
			max_uses: Number(form.max_uses),
			duration_days: Number(form.duration_days),
			tier: form.tier || null,
			memo: form.memo || null
		};

		const created = await createAdminRedemptionCodes(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (created) {
			generatedCodes = created.raw_codes ?? [];
			toast.success('Redeem code created.');
			await load();
		}
		creating = false;
	};

	onMount(load);
</script>

<div class="flex flex-col gap-4">
	<div>
		<div class="text-base font-medium">Redeem Codes</div>
		<div class="text-xs text-gray-500">Generate codes for subscription time and Chatpoint grants.</div>
	</div>

	<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
		<div class="grid gap-2 md:grid-cols-4">
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Mode</span>
				<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.mode}>
					<option value="single_use">Single Use</option>
					<option value="multi_use">Multi Use</option>
				</select>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Quantity</span>
				<input type="number" min="1" class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 disabled:text-gray-400 dark:border-gray-850" disabled={form.mode === 'multi_use'} bind:value={form.quantity} />
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Max Uses</span>
				<input type="number" min="1" class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.max_uses} />
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Tier</span>
				<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.tier}>
					<option value="">No Tier Change</option>
					<option value="free">Free</option>
					<option value="plus">Plus</option>
					<option value="chatpower">ChatPower</option>
				</select>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Duration Days</span>
				<input type="number" min="0" class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.duration_days} />
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Plan Chatpoint</span>
				<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.plan_chatpoint} />
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Check Chatpoint</span>
				<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.check_chatpoint} />
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Memo</span>
				<input class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={form.memo} />
			</label>
		</div>
		<div class="mt-3 flex justify-end">
			<button type="button" class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black" disabled={creating} on:click={createCodes}>
				{creating ? 'Creating' : 'Create Codes'}
			</button>
		</div>
	</div>

	{#if generatedCodes.length > 0}
		<div class="rounded-lg border border-green-200 p-3 text-xs dark:border-green-900">
			<div class="mb-2 font-medium">Generated Codes</div>
			<div class="grid gap-1 font-mono">
				{#each generatedCodes as code}
					<div>{code}</div>
				{/each}
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="text-gray-500">Loading...</div>
	{:else if codes.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">No redeem codes.</div>
	{:else}
		<div class="flex flex-col divide-y divide-gray-100 rounded-lg border border-gray-100 dark:divide-gray-850 dark:border-gray-850">
			{#each codes as code}
				<div class="grid gap-2 p-3 text-xs md:grid-cols-[1fr_7rem_7rem_8rem_7rem]">
					<div>
						<div class="font-mono font-medium">{code.code_preview}</div>
						<div class="text-gray-500">{code.memo ?? '-'}</div>
					</div>
					<div>{code.mode}</div>
					<div>{code.used_count}/{code.max_uses}</div>
					<div>{code.tier ?? 'No tier'} · {code.duration_days ?? 0}d</div>
					<div>{formatChatpoint(code.plan_chatpoint_micros + code.check_chatpoint_micros)} CP</div>
					<div class="md:col-span-5 text-gray-500">Expires: {formatDate(code.expires_at)}</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
