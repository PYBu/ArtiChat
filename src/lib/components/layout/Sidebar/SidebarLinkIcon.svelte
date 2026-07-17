<script lang="ts">
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import BookOpen from '$lib/components/icons/BookOpen.svelte';
	import Calendar from '$lib/components/icons/Calendar.svelte';
	import ChatBubble from '$lib/components/icons/ChatBubble.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
	import Grid from '$lib/components/icons/Grid.svelte';
	import Home from '$lib/components/icons/Home.svelte';
	import Link from '$lib/components/icons/Link.svelte';
	import QuestionMarkCircle from '$lib/components/icons/QuestionMarkCircle.svelte';
	import Star from '$lib/components/icons/Star.svelte';

	export let icon = 'link';
	export let className = 'size-4.5';

	const icons = {
		link: Link,
		globe: GlobeAlt,
		home: Home,
		document: Document,
		book: BookOpen,
		chat: ChatBubble,
		star: Star,
		bolt: Bolt,
		calendar: Calendar,
		cube: Cube,
		grid: Grid,
		help: QuestionMarkCircle
	};

	$: component = icons[icon] ?? Link;
</script>

<svelte:component this={component} {className} />
