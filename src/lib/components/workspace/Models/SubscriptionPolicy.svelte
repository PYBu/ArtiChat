<script lang="ts">
	export let policy = {
		allowed_tiers: ['free', 'plus', 'chatpower'],
		quota_mode: 'metered',
		usage_multiplier: '1'
	};

	const tiers = [
		{ id: 'free', label: 'Free' },
		{ id: 'plus', label: 'Plus' },
		{ id: 'chatpower', label: 'ChatPower' }
	];

	const toggleTier = (tier: string) => {
		policy.allowed_tiers = policy.allowed_tiers ?? ['free', 'plus', 'chatpower'];
		const allowed = new Set(policy.allowed_tiers ?? []);
		if (allowed.has(tier)) {
			allowed.delete(tier);
		} else {
			allowed.add(tier);
		}
		policy.allowed_tiers = tiers.map((item) => item.id).filter((item) => allowed.has(item));
		policy = policy;
	};
</script>

<div id="model-subscription-policy" class="flex flex-col gap-2 text-sm">
	<div class="flex w-full justify-between">
		<div>
			<div class="text-xs font-medium text-gray-500">Subscription Policy</div>
			<div class="text-xs text-gray-400">Control which plans can see and use this model.</div>
		</div>
	</div>

	<div class="grid gap-2 rounded-lg border border-gray-100 p-3 dark:border-gray-850 md:grid-cols-3">
		<div>
			<div class="mb-2 text-xs text-gray-500">Visible To</div>
			<div class="flex flex-wrap gap-2">
				{#each tiers as tier}
					<label class="flex items-center gap-1 rounded-full bg-gray-50 px-2 py-1 text-xs dark:bg-gray-900">
						<input
							type="checkbox"
							checked={(policy.allowed_tiers ?? []).includes(tier.id)}
							on:change={() => toggleTier(tier.id)}
						/>
						<span>{tier.label}</span>
					</label>
				{/each}
			</div>
		</div>

		<label class="flex flex-col gap-1">
			<span class="text-xs text-gray-500">Quota Mode</span>
			<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={policy.quota_mode}>
				<option value="metered">Metered</option>
				<option value="unlimited">Unlimited</option>
			</select>
		</label>

		<label class="flex flex-col gap-1">
			<span class="text-xs text-gray-500">Usage Multiplier</span>
			<input
				class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 disabled:text-gray-400 dark:border-gray-850"
				disabled={policy.quota_mode === 'unlimited'}
				bind:value={policy.usage_multiplier}
			/>
		</label>
	</div>
</div>
