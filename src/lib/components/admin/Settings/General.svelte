<script lang="ts">
	import DOMPurify from 'dompurify';
	import { v4 as uuidv4 } from 'uuid';

	import { getBackendConfig } from '$lib/apis';
	import { getAdminConfig, updateAdminConfig } from '$lib/apis/auths';
	import { getBanners, setBanners } from '$lib/apis/configs';
	import Switch from '$lib/components/common/Switch.svelte';
	import { banners as _banners, config } from '$lib/stores';
	import type { Banner } from '$lib/types';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import Banners from './Interface/Banners.svelte';
	import Events from './Events.svelte';

	const i18n = getContext('i18n');

	export let saveHandler: Function;

	let adminConfig = null;

	let banners: Banner[] = [];

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
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={async () => {
		updateHandler();
	}}
>
	<div class="space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		{#if adminConfig !== null}
			<div class="">
				<div class="mb-3.5">
					<div class=" mt-0.5 mb-2.5 text-base font-medium">{$i18n.t('General')}</div>

					<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2" />

					<div class="mb-2.5">
						<div class="flex w-full justify-between items-center">
							<div class="text-xs pr-2">
								<div class="">
									{$i18n.t('Help')}
								</div>
								<div class="text-xs text-gray-500">
									{$i18n.t('Manage ArtiChat system settings for this deployment.')}
								</div>
							</div>
						</div>
					</div>

					<div class="mb-2.5">
						<div class="flex w-full justify-between items-center">
							<div class="text-xs pr-2">
								<div class="">
									{$i18n.t('License')}
								</div>

								{#if $config?.license_metadata}
									<div class="text-gray-500 mt-0.5">
										<span class="capitalize text-black dark:text-white"
											>{$config?.license_metadata?.type} license</span
										>
										registered to
										<span class="capitalize text-black dark:text-white"
											>{$config?.license_metadata?.organization_name}</span
										>
										for
										<span class="font-medium text-black dark:text-white"
											>{$config?.license_metadata?.seats ?? 'Unlimited'} users.</span
										>
									</div>
									{#if $config?.license_metadata?.html}
										<div class="mt-0.5">
											{@html DOMPurify.sanitize($config?.license_metadata?.html)}
										</div>
									{/if}
								{:else}
									<span class="text-gray-500">
										{$i18n.t('ArtiChat is ready for your local deployment.')}
									</span>
								{/if}
							</div>

							<!-- <button
								class="flex-shrink-0 text-xs px-3 py-1.5 bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition rounded-lg font-medium"
							>
								{$i18n.t('Activate')}
							</button> -->
						</div>
					</div>
				</div>

				<div class="mb-3">
					<div class=" mt-0.5 mb-2.5 text-base font-medium">{$i18n.t('Features')}</div>

					<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2" />

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Enable Community Sharing')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_COMMUNITY_SHARING} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">{$i18n.t('Enable Message Rating')}</div>

						<Switch bind:state={adminConfig.ENABLE_MESSAGE_RATING} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Folders')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_FOLDERS} />
					</div>

					{#if adminConfig.ENABLE_FOLDERS}
						<div class="mb-2.5 w-full justify-between">
							<div class="flex w-full justify-between">
								<div class=" self-center text-xs font-medium">
									{$i18n.t('Folder Max File Count')}
								</div>
							</div>

							<div class="flex mt-2 space-x-2">
								<input
									class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
									type="number"
									min="0"
									placeholder={$i18n.t('Leave empty for unlimited')}
									bind:value={adminConfig.FOLDER_MAX_FILE_COUNT}
								/>
							</div>

							<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
								{$i18n.t('Maximum number of files allowed per folder.')}
							</div>
						</div>
					{/if}

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Memories')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_MEMORIES} />
					</div>

					{#if adminConfig.ENABLE_MEMORIES}
						<div class="mb-2.5 flex w-full items-center justify-between pr-2 pl-4">
							<div class=" self-center text-xs font-medium text-gray-500 dark:text-gray-400">
								{$i18n.t('Memory System Context')}
							</div>

							<Switch bind:state={adminConfig.ENABLE_MEMORY_SYSTEM_CONTEXT} />
						</div>
					{/if}

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Notes')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_NOTES} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Channels')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_CHANNELS} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Calendar')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_CALENDAR} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Automations')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_AUTOMATIONS} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('User Webhooks')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_USER_WEBHOOKS} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('User Status')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_USER_STATUS} />
					</div>

					<div class="mb-2.5">
						<div class=" self-center text-xs font-medium mb-2">
							{$i18n.t('Response Watermark')}
						</div>
						<Textarea
							placeholder={$i18n.t('Enter a watermark for the response. Leave empty for none.')}
							bind:value={adminConfig.RESPONSE_WATERMARK}
						/>
					</div>

					<div class="mb-2.5 w-full justify-between">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('Application URL')}</div>
						</div>

						<div class="flex mt-2 space-x-2">
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								type="text"
								placeholder={`e.g.) "http://localhost:3000"`}
								bind:value={adminConfig.WEBUI_URL}
							/>
						</div>

						<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
							{$i18n.t(
								'Enter the public URL of ArtiChat. This URL will be used to generate links in notifications.'
							)}
						</div>
					</div>
				</div>

				<Events />

				<div class="mb-3.5">
					<div class=" mt-0.5 mb-2.5 text-base font-medium">{$i18n.t('UI')}</div>

					<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2" />

					<div class="mb-2.5">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs">
								{$i18n.t('Banners')}
							</div>

							<button
								class="p-1 px-3 text-xs flex rounded-sm transition"
								type="button"
								on:click={() => {
									if (banners.length === 0 || banners.at(-1).content !== '') {
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
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="w-4 h-4"
								>
									<path
										d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z"
									/>
								</svg>
							</button>
						</div>

						<Banners bind:banners />
					</div>
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
