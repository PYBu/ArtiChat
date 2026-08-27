<script>
	import { createEventDispatcher, getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { config as backendConfig, user } from '$lib/stores';
	import { getBackendConfig } from '$lib/apis';
	import { getVideoGenerationConfig, updateVideoGenerationConfig } from '$lib/apis/videos';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import SettingsSelect from '$lib/components/common/SettingsSelect.svelte';
	import AdminSettingField from './AdminSettingField.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import AdminSettingSection from './AdminSettingSection.svelte';

	const dispatch = createEventDispatcher();
	const i18n = getContext('i18n');

	let loading = false;
	let videoConfig = null;
	const inputClass =
		'w-full h-7 rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';
	const textareaClass =
		'w-full rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';

	const updateVideoConfigHandler = async () => {
		if (!videoConfig) return null;

		if (
			videoConfig.ENABLE_VIDEO_GENERATION &&
			!videoConfig.VIDEO_GENERATION_API_KEY &&
			!videoConfig.VIDEO_GENERATION_API_KEY_SET
		) {
			toast.error($i18n.t('启用视频生成时必须填写接口密钥。'));
			videoConfig.ENABLE_VIDEO_GENERATION = false;
			return null;
		}

		const res = await updateVideoGenerationConfig(localStorage.token, videoConfig).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			videoConfig = res;
			backendConfig.set(await getBackendConfig());
		}

		return res;
	};

	const saveHandler = async () => {
		loading = true;
		const res = await updateVideoConfigHandler();
		if (res) dispatch('save');
		loading = false;
	};

	onMount(async () => {
		if ($user?.role !== 'admin') return;
		videoConfig = await getVideoGenerationConfig(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
	});
</script>

<form
	class="flex h-full flex-col justify-between text-sm"
	on:submit|preventDefault={saveHandler}
>
	<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">{$i18n.t('视频')}</h2>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		{#if videoConfig}
			<div class="flex flex-col">
				<AdminSettingSection first>
					<AdminSettingRow
						label={$i18n.t('视频生成')}
						description={$i18n.t('根据文字或首帧图片异步生成视频。')}
						let:labelId
					>
						<Switch bind:state={videoConfig.ENABLE_VIDEO_GENERATION} ariaLabelledbyId={labelId} />
					</AdminSettingRow>

					<AdminSettingRow
						label={$i18n.t('仅管理员')}
						description={$i18n.t('默认仅允许管理员生成视频。')}
						let:labelId
					>
						<Switch bind:state={videoConfig.VIDEO_GENERATION_ADMIN_ONLY} ariaLabelledbyId={labelId} />
					</AdminSettingRow>

					<AdminSettingField
						label={$i18n.t('每秒视频扣除 Chatpoint')}
						description={$i18n.t('视频生成成功后按实际视频秒数计费，失败或取消不扣费。')}
					>
						<input
							type="number"
							min="0"
							step="0.0001"
							class={inputClass}
							bind:value={videoConfig.VIDEO_GENERATION_CHATPOINTS_PER_SECOND}
						/>
					</AdminSettingField>

					<AdminSettingRow
						label={$i18n.t('生成前确认费用')}
						description={$i18n.t('非管理员必须先确认预计费用，模型才会提交视频任务。')}
						let:labelId
					>
						<Switch
							bind:state={videoConfig.VIDEO_GENERATION_REQUIRE_CONFIRMATION}
							ariaLabelledbyId={labelId}
						/>
					</AdminSettingRow>

					<AdminSettingField
						label={$i18n.t('每日视频费用上限（Chatpoint）')}
						description={$i18n.t('设置为 0 表示不启用额外日上限；余额与预留仍会照常校验。')}
					>
						<input
							type="number"
							min="0"
							step="0.0001"
							class={inputClass}
							bind:value={videoConfig.VIDEO_GENERATION_DAILY_MAX_CHATPOINTS}
						/>
					</AdminSettingField>

					<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
						<AdminSettingField label={$i18n.t('服务提供商')}>
							<SettingsSelect bind:value={videoConfig.VIDEO_GENERATION_PROVIDER}>
								<option value="minimax">MiniMax H3 v2</option>
								<option value="seedance">Seedance / ModelArk</option>
							</SettingsSelect>
						</AdminSettingField>

						<AdminSettingField label={$i18n.t('接口版本')}>
							<input class={inputClass} bind:value={videoConfig.VIDEO_GENERATION_API_VERSION} placeholder="v2" />
						</AdminSettingField>

						<AdminSettingField label={$i18n.t('基础地址')}>
							<input
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_BASE_URL}
								placeholder="https://api.minimaxi.com"
							/>
						</AdminSettingField>

						<AdminSettingField label={$i18n.t('接口密钥')}>
							<SensitiveInput
								variant="settings"
								bind:value={videoConfig.VIDEO_GENERATION_API_KEY}
								placeholder={$i18n.t('接口密钥')}
								required={false}
							/>
						</AdminSettingField>

						<AdminSettingField label={$i18n.t('模型')}>
							<input
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_MODEL}
								placeholder="MiniMax-H3"
							/>
						</AdminSettingField>

						{#if videoConfig.VIDEO_GENERATION_PROVIDER === 'seedance'}
							<AdminSettingField label={$i18n.t('区域')}>
								<input
									class={inputClass}
									bind:value={videoConfig.VIDEO_GENERATION_REGION}
									placeholder="cn-beijing"
								/>
							</AdminSettingField>
						{/if}
					</div>

					<div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
						<AdminSettingField label={$i18n.t('分辨率')}>
							<input
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_RESOLUTION}
								placeholder="768P"
							/>
						</AdminSettingField>
						<AdminSettingField label={$i18n.t('时长（秒）')}>
							<input
								type="number"
								min="4"
								max="15"
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_DURATION}
							/>
						</AdminSettingField>
						<AdminSettingField label={$i18n.t('画面比例')}>
							<input
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_RATIO}
								placeholder="16:9"
							/>
						</AdminSettingField>
						<AdminSettingField label={$i18n.t('轮询间隔（秒）')}>
							<input
								type="number"
								min="1"
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_POLL_INTERVAL}
							/>
						</AdminSettingField>
						<AdminSettingField label={$i18n.t('最大并发数')}>
							<input
								type="number"
								min="1"
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_MAX_CONCURRENCY}
							/>
						</AdminSettingField>
						<AdminSettingField label={$i18n.t('最大输出（MB）')}>
							<input
								type="number"
								min="1"
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_MAX_OUTPUT_MB}
							/>
						</AdminSettingField>
						<AdminSettingField label={$i18n.t('最大尝试次数')}>
							<input
								type="number"
								min="1"
								class={inputClass}
								bind:value={videoConfig.VIDEO_GENERATION_MAX_ATTEMPTS}
							/>
						</AdminSettingField>
					</div>

					<AdminSettingRow
						label={$i18n.t('水印')}
						description={$i18n.t('服务提供商支持时请求添加水印。')}
						let:labelId
					>
						<Switch bind:state={videoConfig.VIDEO_GENERATION_WATERMARK} ariaLabelledbyId={labelId} />
					</AdminSettingRow>

					<AdminSettingRow
						label={$i18n.t('视频提示词生成')}
						description={$i18n.t('允许模型在生成前优化视频提示词。')}
						let:labelId
					>
						<Switch bind:state={videoConfig.VIDEO_GENERATION_PROMPT_ENABLE} ariaLabelledbyId={labelId} />
					</AdminSettingRow>

					<AdminSettingField
						label={$i18n.t('视频提示词模板')}
						description={$i18n.t('使用 {{PROMPT}} 作为用户请求的插入位置。')}
					>
						<Textarea
							className={textareaClass}
							bind:value={videoConfig.VIDEO_GENERATION_PROMPT_TEMPLATE}
							placeholder={$i18n.t('留空则使用默认视频提示词。')}
							minSize={120}
						/>
					</AdminSettingField>
				</AdminSettingSection>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-6 text-sm font-normal">
		<button
			class="px-3.5 py-1.5 text-sm font-normal bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full flex items-center gap-2 whitespace-nowrap {loading
				? ' cursor-not-allowed'
				: ''}"
			type="submit"
			disabled={loading}
		>
			{$i18n.t('Save')}
			{#if loading}
				<span class="shrink-0"><Spinner /></span>
			{/if}
		</button>
	</div>
</form>
