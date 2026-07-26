<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import type { ReasoningControlConfig, ReasoningProfile } from '$lib/apis';
	import Switch from '$lib/components/common/Switch.svelte';
	import { suggestReasoningProfile } from '$lib/utils/reasoning';

	const i18n: Writable<i18nType> = getContext('i18n');

	export let control: ReasoningControlConfig = { enabled: false, profile: null };
	export let modelId = '';

	$: suggestedProfile = suggestReasoningProfile(modelId);
	$: if (control.enabled && !control.profile && suggestedProfile) {
		control = { ...control, profile: suggestedProfile };
	}

	const setEnabled = (enabled: boolean) => {
		control = {
			...control,
			enabled,
			profile: control.profile ?? (enabled ? suggestedProfile : null)
		};
	};

	const setProfile = (profile: ReasoningProfile) => {
		control = { ...control, profile };
	};
</script>

<div class="my-4 border-y border-gray-100 py-4 dark:border-gray-850">
	<div class="flex items-center justify-between gap-4">
		<div class="text-xs font-medium text-gray-500">{$i18n.t('Reasoning control')}</div>
		<Switch
			state={control.enabled}
			ariaLabel={$i18n.t('Reasoning control')}
			on:change={(event) => setEnabled(event.detail)}
		/>
	</div>

	{#if control.enabled}
		<div class="mt-3">
			<div class="mb-1.5 text-xs text-gray-500">{$i18n.t('Reasoning profile')}</div>
			<div class="grid grid-cols-2 gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-850">
				{#each [['gpt', 'GPT / Codex'], ['claude', 'Claude']] as [profile, label]}
					<button
						type="button"
						class="h-8 rounded-md px-3 text-xs font-medium transition-colors {control.profile ===
						profile
							? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
							: 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-100'}"
						aria-pressed={control.profile === profile}
						on:click={() => setProfile(profile as ReasoningProfile)}
					>
						{label}
					</button>
				{/each}
			</div>
		</div>
	{/if}
</div>
