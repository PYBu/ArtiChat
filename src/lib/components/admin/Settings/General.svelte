<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';

	import { getBackendConfig } from '$lib/apis';
	import { getAdminConfig, updateAdminConfig } from '$lib/apis/auths';
	import { getBanners, setBanners } from '$lib/apis/configs';
	import SettingsSelect from '$lib/components/common/SettingsSelect.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import { banners as _banners, config } from '$lib/stores';
	import type { Banner } from '$lib/types';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import Banners from './Interface/Banners.svelte';
	import Events from './Events.svelte';
	import AdminSettingField from './AdminSettingField.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import AdminSettingSection from './AdminSettingSection.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';

	const i18n: any = getContext('i18n');

	export let saveHandler: Function;

	let adminConfig: any = null;

	let banners: Banner[] = [];
	const inputClass =
		'w-full h-7 rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';
	const textareaClass =
		'w-full rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';

	const updateBanners = async () => {
		_banners.set(await setBanners(localStorage.token, banners));
	};

	const updateHandler = async () => {
		const res = await updateAdminConfig(localStorage.token, adminConfig);

		await updateBanners();

		await config.set(await getBackendConfig());

		if (res) {
			saveHandler();
		} else {
			toast.error($i18n.t('Failed to update settings'));
		}
	};

	onMount(async () => {
		adminConfig = await getAdminConfig(localStorage.token);

		banners = [...$_banners];
	});
</script>

<form
	class="flex h-full flex-col justify-between text-sm"
	on:submit|preventDefault={async () => {
		updateHandler();
	}}
>
	<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">{$i18n.t('General')}</h2>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		{#if adminConfig !== null}
			<AdminSettingSection first>
				<div class="text-xs">
					<div class="text-gray-600 dark:text-gray-400">{$i18n.t('Project')}</div>
					<a
						class="mt-0.5 block text-gray-500 transition-colors hover:text-gray-900 dark:hover:text-white"
						href="https://github.com/PYBu/ArtiChat"
						target="_blank"
					>
						{$i18n.t('Source code and documentation')}
					</a>
				</div>
			</AdminSettingSection>

			<AdminSettingSection title={$i18n.t('Features')}>
				<AdminSettingRow
					label={$i18n.t('Message Rating')}
					description={$i18n.t('Let users rate assistant responses.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_MESSAGE_RATING} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				<AdminSettingRow
					label={$i18n.t('Folders')}
					description={$i18n.t('Allow users to organize chats into folders.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_FOLDERS} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				{#if adminConfig.ENABLE_FOLDERS}
					<AdminSettingField
						label={$i18n.t('Folder Max File Count')}
						description={$i18n.t('Maximum number of files allowed per folder.')}
					>
						<input
							class={inputClass}
							type="number"
							min="0"
							placeholder={$i18n.t('Leave empty for unlimited')}
							bind:value={adminConfig.FOLDER_MAX_FILE_COUNT}
						/>
					</AdminSettingField>
				{/if}

				<AdminSettingRow
					label={$i18n.t('Memories')}
					description={$i18n.t('Allow users to save memories for more personalized responses.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_MEMORIES} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				{#if adminConfig.ENABLE_MEMORIES}
					<AdminSettingRow
						label={$i18n.t('Memory System Context')}
						description={$i18n.t('Include saved memories in the system context.')}
						labelClassName="text-gray-500 dark:text-gray-500"
						let:labelId
					>
						<Switch
							bind:state={adminConfig.ENABLE_MEMORY_SYSTEM_CONTEXT}
							ariaLabelledbyId={labelId}
						/>
					</AdminSettingRow>
				{/if}
				<AdminSettingRow
					label={$i18n.t('Notes')}
					description={$i18n.t('Allow users to create and manage notes.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_NOTES} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				<AdminSettingRow
					label={$i18n.t('Channels')}
					description={$i18n.t('Allow users to use channels for shared conversations.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_CHANNELS} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				{#if adminConfig.ENABLE_CHANNELS}
					<AdminSettingRow
						label={$i18n.t('Model Response Mode')}
						description={$i18n.t(
							'Choose where model responses to root-level channel mentions are posted.'
						)}
						labelClassName="text-gray-500 dark:text-gray-500"
						let:labelId
					>
						<SettingsSelect
							bind:value={adminConfig.CHANNEL_MODEL_RESPONSE_MODE}
							aria-labelledby={labelId}
						>
							<option value="thread">{$i18n.t('Thread')}</option>
							<option value="channel">{$i18n.t('Channel')}</option>
						</SettingsSelect>
					</AdminSettingRow>
				{/if}
				<AdminSettingRow
					label={$i18n.t('Calendar')}
					description={$i18n.t('Allow users to access calendar features.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_CALENDAR} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				<AdminSettingRow
					label={$i18n.t('Automations')}
					description={$i18n.t('Allow users to create and run automations.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_AUTOMATIONS} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				<AdminSettingRow
					label={$i18n.t('User Webhooks')}
					description={$i18n.t('Allow users to configure webhooks from their account.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_USER_WEBHOOKS} ariaLabelledbyId={labelId} />
				</AdminSettingRow>
				<AdminSettingRow
					label={$i18n.t('User Status')}
					description={$i18n.t('Show user status information in the app.')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_USER_STATUS} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				<AdminSettingField
					label={$i18n.t('Response Watermark')}
					description={$i18n.t('Append a watermark to assistant responses when configured.')}
				>
					<Textarea
						className={textareaClass}
						placeholder={$i18n.t('Enter a watermark for the response. Leave empty for none.')}
						bind:value={adminConfig.RESPONSE_WATERMARK}
					/>
				</AdminSettingField>

				<AdminSettingField
					label={$i18n.t('WebUI URL')}
					description={$i18n.t(
						'Enter the public URL of your WebUI. This URL will be used to generate links in the notifications.'
					)}
				>
					<input
						class={inputClass}
						type="text"
						placeholder={`e.g.) "http://localhost:3000"`}
						bind:value={adminConfig.WEBUI_URL}
					/>
				</AdminSettingField>
			</AdminSettingSection>

			<AdminSettingSection title={$i18n.t('Billing')}>
				<AdminSettingField
					label={$i18n.t('Pending settlement conversation limit')}
					description={$i18n.t(
						'Number of conversations a user may start while Chatpoint settlement is pending. Set to 0 to settle synchronously.'
					)}
				>
					<input
						class={inputClass}
						type="number"
						min="0"
						max="100"
						step="1"
						bind:value={adminConfig.MAX_PENDING_SETTLEMENTS_PER_USER}
					/>
				</AdminSettingField>
			</AdminSettingSection>

			<Events />

			<AdminSettingSection title={$i18n.t('UI')}>
				<div>
					<div class="mb-2 flex w-full items-start justify-between gap-4">
						<div class="min-w-0">
							<div class="text-xs text-gray-600 dark:text-gray-400">{$i18n.t('Banners')}</div>
							<div class="mt-1.5 text-[0.6875rem] text-gray-400 dark:text-gray-600">
								{$i18n.t('Create announcements shown to users in the app.')}
							</div>
						</div>

						<button
							class="flex size-6 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-black/5 hover:text-gray-900 dark:text-gray-600 dark:hover:bg-white/5 dark:hover:text-white"
							type="button"
							aria-label={$i18n.t('Add banner')}
							on:click={() => {
								if (banners.length === 0 || banners[banners.length - 1]?.content !== '') {
									banners = [
										...banners,
										{
											id: uuidv4(),
											type: '',
											title: '',
											content: '',
											dismissible: true,
											timestamp: Math.floor(Date.now() / 1000)
										}
									];
								}
							}}
						>
							<Plus />
						</button>
					</div>

					<Banners bind:banners />
				</div>
			</AdminSettingSection>
		{/if}
	</div>

	<div class="flex justify-end pt-6 text-sm font-normal">
		<button
			class="px-3.5 py-1.5 text-sm font-normal bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
