<script lang="ts">
	import SubscriptionPageShell from '$lib/components/admin/Subscriptions/SubscriptionPageShell.svelte';
	import AccessRestrictions from '$lib/components/admin/Settings/Subscriptions/AccessRestrictions.svelte';
</script>

<SubscriptionPageShell
	title="限制管理"
	description="限制国家或 IP 的新登录与注册，并查看最近 7 天登录记录。"
>
	<AccessRestrictions />
</SubscriptionPageShell>
