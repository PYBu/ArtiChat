<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { config } from '$lib/stores';

	export let kind: 'mark' | 'splash' = 'mark';
	export let className = '';
	export let alt = '';
	export let draggable = false;

	$: lightFile = kind === 'splash' ? 'splash.png' : 'favicon.png';
	$: darkFile = kind === 'splash' ? 'splash-dark.png' : 'favicon-dark.png';
	$: configuredLight = $config?.branding?.logo_light;
	$: configuredDark = $config?.branding?.logo_dark;
	$: lightSrc = configuredLight || `${WEBUI_BASE_URL}/static/${lightFile}`;
	$: darkSrc = configuredDark || `${WEBUI_BASE_URL}/static/${darkFile}`;
</script>

<span class="inline-flex items-center justify-center">
	<img
		crossorigin="anonymous"
		src={lightSrc}
		class={`${className} dark:hidden`}
		{alt}
		{draggable}
	/>
	<img
		crossorigin="anonymous"
		src={darkSrc}
		class={`${className} hidden dark:block`}
		{alt}
		{draggable}
	/>
</span>
