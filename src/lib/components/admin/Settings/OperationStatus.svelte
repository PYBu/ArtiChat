<script lang="ts">
	import { createEventDispatcher, getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { config as backendConfig, user } from '$lib/stores';
	import { getBackendConfig } from '$lib/apis';
	import { getOperationStatusConfig, updateOperationStatusConfig } from '$lib/apis/operationStatus';
	import {
		getDefaultOperationStatusConfig,
		OPERATION_STATUS_CATALOG,
		OPERATION_STATUS_GROUPS,
		type OperationStatusConfig
	} from '$lib/utils/operationStatus';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import AdminSettingField from './AdminSettingField.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import AdminSettingSection from './AdminSettingSection.svelte';

	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');

	const inputClass =
		'w-full h-7 rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';

	let loading = false;
	let statusConfig: OperationStatusConfig | null = null;

	const withDefaults = (value: OperationStatusConfig | null | undefined): OperationStatusConfig => {
		const defaults = getDefaultOperationStatusConfig();
		const entries = { ...defaults.entries, ...(value?.entries ?? {}) };
		// The server stores the English built-in text for compatibility. Treat those
		// values as unset so the field can show the current locale's translated hint.
		for (const item of OPERATION_STATUS_CATALOG) {
			if (entries[item.id]?.text === item.defaultText)
				entries[item.id] = { ...entries[item.id], text: '' };
		}
		return {
			enabled: value?.enabled ?? defaults.enabled,
			deduplicate: value?.deduplicate ?? defaults.deduplicate,
			entries
		};
	};

	const saveHandler = async () => {
		if (!statusConfig) return;
		loading = true;
		try {
			statusConfig = withDefaults(
				await updateOperationStatusConfig(localStorage.token, withDefaults(statusConfig))
			);
			await backendConfig.set(await getBackendConfig());
			dispatch('save');
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			loading = false;
		}
	};

	onMount(async () => {
		if ($user?.role !== 'admin') return;
		try {
			statusConfig = withDefaults(await getOperationStatusConfig(localStorage.token));
		} catch (error) {
			toast.error(`${error}`);
			statusConfig = withDefaults(null);
		}
	});
</script>

<form class="flex h-full flex-col justify-between text-sm" on:submit|preventDefault={saveHandler}>
	<div class="flex items-center justify-between mb-4">
		<h2 class="text-sm font-medium text-gray-900 dark:text-white">{$i18n.t('Operation Status')}</h2>
		<button
			type="submit"
			class="h-7 rounded-lg bg-gray-900 px-3 text-xs text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
			disabled={loading || !statusConfig}
		>
			{#if loading}<Spinner className="size-3.5" />{:else}{$i18n.t('Save')}{/if}
		</button>
	</div>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		{#if statusConfig}
			<AdminSettingSection first title={$i18n.t('Global behavior')}>
				<AdminSettingRow
					label={$i18n.t('Show operation status')}
					description={$i18n.t('Turn this off to hide all operation status rows for users.')}
					let:labelId
				>
					<Switch bind:state={statusConfig.enabled} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				<AdminSettingRow
					label={$i18n.t('Merge repeated statuses')}
					description={$i18n.t(
						'Repeated polling updates replace the previous row instead of creating a long history.'
					)}
					let:labelId
				>
					<Switch bind:state={statusConfig.deduplicate} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
			</AdminSettingSection>

			{#each OPERATION_STATUS_GROUPS as group}
				<AdminSettingSection title={$i18n.t(group.group)} first={false}>
					{#each group.items as item}
						<AdminSettingRow
							label={$i18n.t(item.label)}
							description={$i18n.t(item.description)}
							let:labelId
						>
							<Switch
								bind:state={statusConfig.entries[item.id].visible}
								ariaLabelledbyId={labelId}
							/>
						</AdminSettingRow>
						<AdminSettingField
							label={$i18n.t('Custom text')}
							description={$i18n.t(
								'Leave empty to use the built-in text. Placeholders such as {{NAME}} and {{COUNT}} are supported.'
							)}
							className="ml-4"
						>
							<input
								class={inputClass}
								bind:value={statusConfig.entries[item.id].text}
								placeholder={$i18n.t(item.defaultText || 'Built-in text', {
									NAME: '{{NAME}}',
									COUNT: '{{COUNT}}',
									DURATION: '{{DURATION}}',
									ERROR: '{{ERROR}}',
									QUERY: '{{QUERY}}'
								})}
								maxlength="500"
							/>
						</AdminSettingField>
					{/each}
				</AdminSettingSection>
			{/each}
		{/if}
	</div>
</form>
