<script lang="ts">
	export let policy = {
		allowed_tiers: ['free', 'plus', 'chatpower'],
		quota_mode: 'metered',
		usage_multiplier: '1',
		input_chatpoint_per_million: '100',
		output_chatpoint_per_million: '100',
		cache_creation_chatpoint_per_million: '0',
		cache_read_chatpoint_per_million: '0'
	};

	const priceFields = [
		{ key: 'input_chatpoint_per_million', label: '输入' },
		{ key: 'output_chatpoint_per_million', label: '输出' },
		{ key: 'cache_creation_chatpoint_per_million', label: '创建缓存' },
		{ key: 'cache_read_chatpoint_per_million', label: '读取缓存' }
	];

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
			<div class="text-xs font-medium text-gray-500">订阅策略</div>
			<div class="text-xs text-gray-400">控制哪些订阅档位可以看到并使用这个模型。</div>
		</div>
	</div>

	<div class="grid gap-3 rounded-lg border border-gray-100 p-3 dark:border-gray-850 md:grid-cols-2">
		<div>
			<div class="mb-2 text-xs text-gray-500">可见范围</div>
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
			<span class="text-xs text-gray-500">扣费模式</span>
			<select class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850" bind:value={policy.quota_mode}>
				<option value="metered">按量扣费</option>
				<option value="unlimited">无限使用</option>
			</select>
		</label>


		<div class="grid grid-cols-2 gap-2 md:col-span-2 md:grid-cols-4">
			{#each priceFields as field}
				<label class="flex min-w-0 flex-col gap-1">
					<span class="text-xs text-gray-500">{field.label}</span>
					<input
						type="number"
						min="0"
						step="any"
						class="min-w-0 rounded-lg border border-gray-100 bg-transparent px-2 py-1 disabled:text-gray-400 dark:border-gray-850"
						disabled={policy.quota_mode === 'unlimited'}
						bind:value={policy[field.key]}
					/>
					<span class="text-[10px] text-gray-400">Chatpoint / 1M Token</span>
				</label>
			{/each}
		</div>
	</div>
</div>
