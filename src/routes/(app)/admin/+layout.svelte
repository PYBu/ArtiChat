<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';

	import { WEBUI_NAME, config, mobile, showSidebar, user } from '$lib/stores';
	import { page } from '$app/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	import Sidebar from '$lib/components/icons/Sidebar.svelte';

	const i18n = getContext('i18n');

	let loaded = false;

	$: adminSection = $page.url.pathname.startsWith('/admin/subscriptions')
		? '/admin/subscriptions'
		: $page.url.pathname.startsWith('/admin/analytics')
			? '/admin/analytics'
			: $page.url.pathname.startsWith('/admin/evaluations')
				? '/admin/evaluations'
				: $page.url.pathname.startsWith('/admin/functions')
					? '/admin/functions'
					: $page.url.pathname.startsWith('/admin/settings')
						? '/admin/settings'
						: '/admin';

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/');
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Admin Panel')} • {$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	<div
		class=" flex flex-col h-screen max-h-[100dvh] flex-1 transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-var(--sidebar-width))]'
			: ' md:max-w-[calc(100%-49px)]'}  w-full max-w-full"
	>
		<nav class="   px-2.5 pt-1.5 backdrop-blur-xl drag-region select-none">
			<div class=" flex items-center gap-1">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center self-end">
						<Tooltip
							content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
							interactive={true}
						>
							<button
								id="sidebar-toggle-button"
								class=" cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition cursor-"
								on:click={() => {
									showSidebar.set(!$showSidebar);
								}}
							>
								<div class=" self-center p-1.5">
									<Sidebar />
								</div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div class="flex w-full min-w-0">
					{#if $mobile}
						<select
							id="admin-mobile-section"
							class="min-w-0 flex-1 rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-sm dark:border-gray-850"
							value={adminSection}
							on:change={(event) => goto(event.currentTarget.value)}
							aria-label="管理员功能"
						>
							<option value="/admin">用户</option>
							{#if $config?.features.enable_admin_analytics ?? true}<option value="/admin/analytics">分析</option>{/if}
							<option value="/admin/evaluations">评估</option>
							<option value="/admin/functions">函数</option>
							<option value="/admin/subscriptions">订阅运营</option>
							<option value="/admin/settings">设置</option>
						</select>
					{:else}
					<div
						class="flex gap-1 scrollbar-none overflow-x-auto w-fit text-center text-sm font-medium rounded-full bg-transparent pt-1"
					>
						<a
							draggable="false"
							class="min-w-fit p-1.5 {$page.url.pathname.includes('/admin/subscriptions')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin/subscriptions">订阅运营</a
						>

						<a
							draggable="false"
							class="min-w-fit p-1.5 {$page.url.pathname.includes('/admin/users')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin">{$i18n.t('Users')}</a
						>

						{#if $config?.features.enable_admin_analytics ?? true}
							<a
								draggable="false"
								class="min-w-fit p-1.5 {$page.url.pathname.includes('/admin/analytics')
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
								href="/admin/analytics">{$i18n.t('Analytics')}</a
							>
						{/if}

						<a
							draggable="false"
							class="min-w-fit p-1.5 {$page.url.pathname.includes('/admin/evaluations')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin/evaluations">{$i18n.t('Evaluations')}</a
						>

						<a
							draggable="false"
							class="min-w-fit p-1.5 {$page.url.pathname.includes('/admin/functions')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin/functions">{$i18n.t('Functions')}</a
						>

						<a
							draggable="false"
							class="min-w-fit p-1.5 {$page.url.pathname.includes('/admin/settings')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin/settings">{$i18n.t('Settings')}</a
						>
					</div>
					{/if}
				</div>
			</div>
		</nav>

		<div class="  pb-1 flex-1 max-h-full overflow-y-auto">
			<slot />
		</div>
	</div>
{/if}
