<script lang="ts">
	export let className = 'size-4';
	export let strokeWidth = '2';
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	fill="none"
	viewBox="0 0 24 24"
	stroke-width={strokeWidth}
	stroke="currentColor"
	aria-hidden="true"
	class={className}
>
	<path stroke-linecap="round" stroke-linejoin="round" d="M12 8v13" />
	<path stroke-linecap="round" stroke-linejoin="round" d="M3 12h18" />
	<path
		stroke-linecap="round"
		stroke-linejoin="round"
		d="M5 8h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z"
	/>
	<path
		stroke-linecap="round"
		stroke-linejoin="round"
		d="M12 8H7.5a2.5 2.5 0 1 1 2.5-2.5C10 7.5 12 8 12 8Zm0 0h4.5a2.5 2.5 0 1 0-2.5-2.5C14 7.5 12 8 12 8Z"
	/>
</svg>
