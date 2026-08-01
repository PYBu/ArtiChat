<script lang="ts">
	import { WEBUI_VERSION } from '$lib/constants';
	import { config } from '$lib/stores';
	import { getContext } from 'svelte';

	import UserSettingSection from './UserSettingSection.svelte';

	const i18n = getContext('i18n');

	const DEFAULT_ABOUT_TITLE = `ArtiChat ProEdition v${WEBUI_VERSION}`;
	const DEFAULT_ABOUT_CONTENT =
		'欢迎使用ArtiChat ProEdition（0.2+），ArtiChat 是一个可私有化部署的功能丰富的AI对话平台。';
	$: aboutTitle = $config?.branding?.about_title?.trim() || DEFAULT_ABOUT_TITLE;
	$: aboutContent = $config?.branding?.about_content?.trim() || DEFAULT_ABOUT_CONTENT;
</script>

<div id="tab-about" class="flex h-full flex-col justify-between text-sm">
	<h2 class="mb-4 text-sm font-medium text-gray-900 dark:text-white">{$i18n.t('About')}</h2>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		<UserSettingSection title={aboutTitle} first>
			<div class="whitespace-pre-wrap text-xs leading-5 text-gray-600 dark:text-gray-400">
				{aboutContent}
			</div>
		</UserSettingSection>
	</div>
</div>
