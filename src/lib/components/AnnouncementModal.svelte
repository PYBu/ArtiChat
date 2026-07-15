<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getActiveAnnouncements,
		markAnnouncementViewed,
		type Announcement
	} from '$lib/apis/announcements';
	import Modal from '$lib/components/common/Modal.svelte';

	const fallbackImageUrl = '/assets/images/space.jpg';

	let queue: Announcement[] = [];
	let show = false;
	let expanded = false;

	const sessionKey = (announcement: Announcement) => `announcement-session-seen:${announcement.id}`;

	const load = async () => {
		if (!localStorage.token) return;
		const response = await getActiveAnnouncements(localStorage.token).catch(() => ({ items: [] }));
		queue = (response?.items ?? []).filter((item) => {
			if (item.display_mode !== 'every_login') return true;
			return sessionStorage.getItem(sessionKey(item)) !== 'true';
		});
		expanded = false;
		show = queue.length > 0;
	};

	const expandCurrent = () => {
		expanded = true;
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
		expanded = false;
		show = queue.length > 0;
	};

	const useFallbackImage = (event: Event) => {
		const image = event.currentTarget as HTMLImageElement;
		if (!image.src.endsWith(fallbackImageUrl)) image.src = fallbackImageUrl;
	};

	onMount(load);

	$: current = queue[0];
</script>

{#if current}
	<Modal
		bind:show
		size="full"
		containerClassName="p-3 sm:p-5"
		className="announcement-shell {expanded
			? 'announcement-expanded'
			: ''} !overflow-hidden !rounded-[18px] !border-0 bg-white dark:bg-gray-900"
		closeOnBackdrop={false}
		closeOnEscape={false}
	>
		<article class="flex max-h-[inherit] min-h-0 flex-col text-gray-900 dark:text-gray-100">
			<div class="announcement-media relative shrink-0 overflow-hidden bg-gray-900">
				<img
					src={current.image_url?.trim() || fallbackImageUrl}
					alt=""
					class="block h-full min-h-[inherit] w-full object-cover object-center"
					on:error={useFallbackImage}
				/>
				<div
					class="pointer-events-none absolute inset-x-0 bottom-0 h-3/5 bg-gradient-to-b from-transparent to-black/75"
				></div>
				<h2
					class="absolute right-5 bottom-5 left-5 m-0 break-words text-center text-xl font-bold leading-tight text-white [text-shadow:0_2px_18px_rgb(0_0_0_/_55%)] sm:right-7 sm:bottom-6 sm:left-7 sm:text-2xl"
				>
					{current.title}
				</h2>
			</div>

			<div class="min-h-0 flex-1 overflow-y-auto px-5 pt-5 sm:px-6 sm:pt-6">
				<p
					class="m-0 whitespace-pre-wrap break-words text-center text-sm leading-7 text-gray-600 dark:text-gray-300"
				>
					{current.summary || current.body}
				</p>

				{#if expanded}
					<div
						class="mt-5 border-t border-gray-100 pt-5 pb-2 whitespace-pre-wrap break-words text-sm leading-7 text-gray-800 dark:border-gray-800 dark:text-gray-200"
					>
						{current.body}
					</div>
				{/if}
			</div>

			<div
				class="grid shrink-0 gap-2.5 px-5 pt-5 pb-5 sm:px-6 sm:pt-6 sm:pb-6 {expanded
					? 'grid-cols-1 justify-items-end'
					: 'grid-cols-2'}"
			>
				{#if !expanded}
					<button
						class="flex min-h-10 min-w-0 items-center justify-center rounded-md bg-gray-900 px-3 py-2 text-sm font-semibold text-white hover:bg-black dark:bg-white dark:text-gray-900 dark:hover:bg-gray-100"
						type="button"
						on:click={expandCurrent}
					>
						<span class="min-w-0 break-words text-center leading-5"
							>{current.view_button_label || '查看公告'}</span
						>
						<span class="ml-2 shrink-0" aria-hidden="true">→</span>
					</button>
				{/if}
				<button
					class="flex min-h-10 min-w-0 items-center justify-center rounded-md border border-gray-200 bg-gray-100 px-3 py-2 text-sm font-semibold text-gray-800 hover:bg-gray-200 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100 dark:hover:bg-gray-700 {expanded
						? 'w-full sm:w-52'
						: ''}"
					type="button"
					on:click={closeCurrent}
				>
					<span class="min-w-0 break-words text-center leading-5"
						>{current.close_button_label || '关闭'}</span
					>
				</button>
			</div>
		</article>
	</Modal>
{/if}

<style>
	:global(.announcement-shell) {
		width: min(460px, calc(100vw - 24px)) !important;
		max-height: min(760px, calc(100dvh - 24px));
		transition:
			width 180ms ease,
			max-height 180ms ease;
	}

	:global(.announcement-shell.announcement-expanded) {
		width: min(720px, calc(100vw - 24px)) !important;
		max-height: min(860px, calc(100dvh - 24px));
	}

	.announcement-media {
		min-height: 270px;
	}

	:global(.announcement-shell.announcement-expanded) .announcement-media {
		min-height: 250px;
	}

	@media (max-width: 720px) {
		.announcement-media,
		:global(.announcement-shell.announcement-expanded) .announcement-media {
			min-height: 218px;
		}
	}
</style>
