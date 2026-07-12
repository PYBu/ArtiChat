<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';

	export let kind: 'mark' | 'splash' = 'mark';
	export let className = '';
	export let alt = '';
	export let draggable = false;

	$: lightFile = kind === 'splash' ? 'splash.png' : 'favicon.png';
	$: darkFile = kind === 'splash' ? 'splash-dark.png' : 'favicon-dark.png';
</script>

<span class="inline-flex items-center justify-center">
	<img
		crossorigin="anonymous"
		src={`${WEBUI_BASE_URL}/static/${lightFile}`}
		class={`${className} dark:hidden`}
		{alt}
		{draggable}
	/>
	<img
		crossorigin="anonymous"
		src={`${WEBUI_BASE_URL}/static/${darkFile}`}
		class={`${className} hidden dark:block`}
		{alt}
		{draggable}
	/>
</span>
