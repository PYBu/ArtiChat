<script lang="ts">
	import { getOllamaVersion } from '$lib/apis/ollama';
	import { WEBUI_BUILD_HASH, WEBUI_DISPLAY_VERSION } from '$lib/constants';
	import { WEBUI_NAME, config, showChangelog } from '$lib/stores';
	import { onMount, getContext } from 'svelte';

	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext('i18n');

	let ollamaVersion = '';

	onMount(async () => {
		ollamaVersion = await getOllamaVersion(localStorage.token).catch((error) => {
			return '';
		});
	});
</script>

<div id="tab-about" class="flex flex-col h-full justify-between space-y-3 text-sm">
	<div class=" space-y-3 overflow-y-scroll max-h-[28rem] md:max-h-full">
		<div>
			<div class=" mb-2.5 text-sm font-medium flex space-x-2 items-center">
				<div>
					{$WEBUI_NAME}
					{$i18n.t('Version')}
				</div>
			</div>
			<div class="flex w-full justify-between items-center">
				<div class="flex flex-col text-xs text-gray-700 dark:text-gray-200">
					<div class="flex gap-1">
						<Tooltip content={WEBUI_BUILD_HASH}>
							v{WEBUI_DISPLAY_VERSION}
						</Tooltip>
					</div>

					<button
						class=" underline flex items-center space-x-1 text-xs text-gray-500 dark:text-gray-500"
						on:click={() => {
							showChangelog.set(true);
						}}
					>
						<div>{$i18n.t("See what's new")}</div>
					</button>
				</div>
			</div>
		</div>

		{#if ollamaVersion}
			<hr class=" border-gray-100/30 dark:border-gray-850/30" />

			<div>
				<div class=" mb-2.5 text-sm font-medium">{$i18n.t('Ollama Version')}</div>
				<div class="flex w-full">
					<div class="flex-1 text-xs text-gray-700 dark:text-gray-200">
						{ollamaVersion ?? 'N/A'}
					</div>
				</div>
			</div>
		{/if}

		<hr class=" border-gray-100/30 dark:border-gray-850/30" />

		{#if $config?.license_metadata}
			<div class="mb-2 text-xs">
				<span class="text-gray-500 dark:text-gray-300 font-medium">{$WEBUI_NAME}</span>
				<span class="capitalize">{$config?.license_metadata?.type}</span> license registered to
				<span class="capitalize">{$config?.license_metadata?.organization_name}</span>
			</div>
		{:else}
			<div class="text-xs text-gray-500 dark:text-gray-400">
				ArtiChat 是一个 AI 多模型聚合平台，主要为用户提供 AI 模型对话服务。
			</div>
		{/if}

		<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
			- ArtiChat 聚合了OpenAI、Anthropic、Google以及X等企业的模型。
		</div>
		<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
			- 平台部分模型永久免费使用，若有更高级的需求可以尝试订阅我们的服务。
		</div>
		<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
			- 模型提供商为Artivis旗下 <b>MineAPI</b> AI服务。
		</div>

		<div>
			<pre
				class="text-xs text-gray-400 dark:text-gray-500">Copyright (c) {new Date().getFullYear()} Artivis | Artivis Studio. All rights reserved.</pre>
		</div>
	</div>
</div>
