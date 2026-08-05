<script lang="ts">
	import { getContext } from 'svelte';
	import SubscriptionCenter from '$lib/components/chat/Settings/SubscriptionCenter.svelte';

	const i18n = getContext('i18n');
</script>

<svelte:head><title>{$i18n.t('Subscription center')}</title></svelte:head>

<SubscriptionCenter />
