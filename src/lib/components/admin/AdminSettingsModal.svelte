<script lang="ts">
	import { user } from '$lib/stores';
	import type { SettingsModalRequest } from '$lib/stores';
	import Modal from '$lib/components/common/Modal.svelte';
	import Settings from './Settings.svelte';

	export let show: boolean | string | SettingsModalRequest = false;

	let modalShow = false;
	let lastShow: boolean | string | SettingsModalRequest = false;
	let selectedTab = 'general';
	let tabState: Record<string, unknown> | null = null;

	const normalizeTab = (tab: string) => tab.replace(/^admin:/, '') || 'general';

	$: if (show !== lastShow) {
		lastShow = show;
		if (show && typeof show === 'object') {
			selectedTab = normalizeTab(show.tab);
			tabState = show.state ?? null;
			show = true;
			lastShow = true;
			modalShow = true;
		} else if (typeof show === 'string') {
			selectedTab = normalizeTab(show);
			show = true;
			lastShow = true;
			modalShow = true;
		} else {
			modalShow = show;
			if (!show) {
				selectedTab = 'general';
				tabState = null;
			}
		}
	}

	$: if ($user?.role !== 'admin' && modalShow) {
		modalShow = false;
	}

	$: if (!modalShow && show !== false) {
		show = false;
		lastShow = false;
		selectedTab = 'general';
		tabState = null;
	}
</script>

<Modal
	size="full"
	containerClassName="p-4 sm:p-6 lg:p-8"
	className="!w-[calc(100vw-2rem)] sm:!w-[calc(100vw-3rem)] lg:!w-[calc(100vw-4rem)] !max-w-[80rem] h-[min(54rem,calc(100dvh-4rem))] max-h-[calc(100dvh-4rem)] flex flex-col bg-white dark:bg-gray-900 rounded-4xl"
	bind:show={modalShow}
>
	<Settings
		modal
		bind:selectedTab
		bind:tabState
		on:close={() => {
			modalShow = false;
		}}
	/>
</Modal>
