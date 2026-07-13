<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getActiveAnnouncements,
		markAnnouncementViewed,
		type Announcement
	} from '$lib/apis/announcements';
	import Modal from '$lib/components/common/Modal.svelte';

	let queue: Announcement[] = [];
	let show = false;

	const sessionKey = (announcement: Announcement) => `announcement-session-seen:${announcement.id}`;

	const load = async () => {
		if (!localStorage.token) return;
		const response = await getActiveAnnouncements(localStorage.token).catch(() => ({ items: [] }));
		queue = (response?.items ?? []).filter((item) => {
			if (item.display_mode !== 'every_login') return true;
			return sessionStorage.getItem(sessionKey(item)) !== 'true';
		});
		show = queue.length > 0;
	};

	const closeCurrent = async () => {
		const current = queue[0];
		if (!current) {
			show = false;
			return;
		}
		if (current.display_mode === 'every_login') {
			sessionStorage.setItem(sessionKey(current), 'true');
		}
		await markAnnouncementViewed(localStorage.token, current.id).catch(() => null);
		queue = queue.slice(1);
		show = queue.length > 0;
	};

	onMount(load);

	$: current = queue[0];
</script>

{#if current}
	<Modal bind:show size="sm" className="bg-white dark:bg-gray-900 rounded-2xl">
		<div class="p-5 text-gray-900 dark:text-gray-100">
			<div class="flex items-start gap-3">
				<div
					class="rounded-xl bg-gray-100 px-2 py-1 text-xs font-medium uppercase dark:bg-gray-850"
				>
					{current.icon ?? 'notice'}
				</div>
				<div class="min-w-0 flex-1">
					<div class="text-lg font-semibold">{current.title}</div>
					<div class="mt-2 whitespace-pre-wrap text-sm leading-6 text-gray-600 dark:text-gray-300">
						{current.body}
					</div>
				</div>
			</div>

			<div class="mt-5 flex justify-end">
				<button
					class="rounded-full bg-black px-4 py-2 text-sm text-white dark:bg-white dark:text-black"
					type="button"
					on:click={closeCurrent}
				>
					{current.button_label ?? '知道了'}
				</button>
			</div>
		</div>
	</Modal>
{/if}
