<script lang="ts">
	import { page } from '$app/stores';
	import SubscriptionPageShell from '$lib/components/admin/Subscriptions/SubscriptionPageShell.svelte';
	import UserSubscriptions from '$lib/components/admin/Settings/Subscriptions/UserSubscriptions.svelte';

	$: requestedUser = $page.url.searchParams.get('user') ?? '';
</script>

<SubscriptionPageShell title="用户订阅" description="查看和编辑用户订阅。">
	<UserSubscriptions initialQuery={requestedUser} />
</SubscriptionPageShell>
