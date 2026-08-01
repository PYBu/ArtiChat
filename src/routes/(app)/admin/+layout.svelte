<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { goto } from '$app/navigation';

	import { WEBUI_NAME, config, mobile, showSidebar, user } from '$lib/stores';
	import { page } from '$app/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	import Sidebar from '$lib/components/icons/Sidebar.svelte';
	import AdminSettingsModal from '$lib/components/admin/AdminSettingsModal.svelte';

	const i18n: Writable<any> = getContext('i18n');

	let loaded = false;
	let showAdminSettings: boolean | string = false;
	$: analyticsEnabled = $config?.features?.enable_admin_analytics ?? true;

	const handleAdminSectionChange = async (event: Event) => {
		const target = (event.currentTarget as HTMLSelectElement).value;
		if (target === '/admin/settings') {
			showAdminSettings = 'general';
			return;
		}
		await goto(target);
	};

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/', { replaceState: true });
		} else if (
			!$config?.features?.enable_plugins &&
			$page.url.pathname.includes('/admin/functions')
		) {
			await goto('/admin', { replaceState: true });
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Admin Panel')} / {$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	<div
		class=" flex flex-col h-screen max-h-[100dvh] flex-1 min-w-0 transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-var(--sidebar-width))]'
			: 'md:max-w-[calc(100%-42px)]'}  w-full max-w-full"
	>
		<nav class="pb-1 px-2.5 pt-2 backdrop-blur-xl drag-region select-none">
			<div class=" flex items-center gap-0.5 md:gap-1">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} self-center flex flex-none items-center">
						<Tooltip
							content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
							interactive={true}
						>
							<button
								id="sidebar-toggle-button"
								class=" cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition cursor-"
								aria-label={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
								on:click={() => {
									showSidebar.set(!$showSidebar);
								}}
							>
								<div class=" self-center p-1.5">
									<Sidebar className="size-4" />
								</div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div class="flex w-full items-center">
					<select
						id="admin-mobile-section"
						class="mr-2 min-w-0 flex-1 bg-transparent px-2 py-1 text-sm outline-hidden md:hidden"
						value={$page.url.pathname.startsWith('/admin/settings')
							? '/admin/settings'
							: $page.url.pathname.startsWith('/admin/subscriptions')
								? '/admin/subscriptions'
								: analyticsEnabled && $page.url.pathname.startsWith('/admin/analytics')
									? '/admin/analytics'
									: $page.url.pathname.startsWith('/admin/evaluations')
										? '/admin/evaluations'
										: $page.url.pathname.startsWith('/admin/functions')
											? '/admin/functions'
											: '/admin'}
						on:change={handleAdminSectionChange}
					>
						<option value="/admin">{$i18n.t('Users')}</option>
						{#if analyticsEnabled}
							<option value="/admin/analytics">{$i18n.t('Analytics')}</option>
						{/if}
						<option value="/admin/evaluations">{$i18n.t('Evaluations')}</option>
						<option value="/admin/subscriptions">{$i18n.t('Operations')}</option>
						{#if $config?.features?.enable_plugins}
							<option value="/admin/functions">{$i18n.t('Functions')}</option>
						{/if}
						<option value="/admin/settings">{$i18n.t('Settings')}</option>
					</select>
					<div
						class="hidden min-w-0 mr-1.5 items-center gap-0.5 md:flex md:gap-1 scrollbar-none overflow-x-auto w-fit text-center text-sm font-normal rounded-full bg-transparent py-1 touch-auto pointer-events-auto"
					>
						<a
							draggable="false"
							class="min-w-fit px-1 text-sm {$page.url.pathname.includes('/admin/users')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin">{$i18n.t('Users')}</a
						>
						{#if analyticsEnabled}
							<a
								draggable="false"
								class="min-w-fit px-1 text-sm {$page.url.pathname.includes('/admin/analytics')
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
								href="/admin/analytics">{$i18n.t('Analytics')}</a
							>
						{/if}

						<a
							draggable="false"
							class="min-w-fit px-1 text-sm {$page.url.pathname.includes('/admin/evaluations')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin/evaluations">{$i18n.t('Evaluations')}</a
						>

						<a
							draggable="false"
							class="min-w-fit px-1 text-sm {$page.url.pathname.includes('/admin/subscriptions')
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin/subscriptions">{$i18n.t('Operations')}</a
						>

						{#if $config?.features?.enable_plugins}
							<a
								draggable="false"
								class="min-w-fit px-1 text-sm {$page.url.pathname.includes('/admin/functions')
									? ''
									: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
								href="/admin/functions">{$i18n.t('Functions')}</a
							>
						{/if}

						<a
							draggable="false"
							class="min-w-fit px-1 text-sm {$page.url.pathname.includes('/admin/settings') ||
							showAdminSettings
								? ''
								: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition select-none"
							href="/admin/settings"
							on:click={(event) => {
								event.preventDefault();
								showAdminSettings = 'general';
							}}>{$i18n.t('Settings')}</a
						>
					</div>
				</div>
			</div>
		</nav>

		<div class="  pb-1 flex-1 min-w-0 max-h-full overflow-y-auto overflow-x-hidden">
			<slot />
		</div>
	</div>

	<AdminSettingsModal bind:show={showAdminSettings} />
{/if}
