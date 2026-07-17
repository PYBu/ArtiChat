<script lang="ts">
	import { onMount } from 'svelte';

	import { getUpdateAnnouncement, type UpdateAnnouncement } from '$lib/apis/updates';
	import VersionUpdatePanel from './VersionUpdatePanel.svelte';

	let announcement: UpdateAnnouncement | null = null;
	let announcementLoading = true;

	const announcementLabels: Record<UpdateAnnouncement['type'], string> = {
		info: '系统公告',
		warning: '重要公告',
		maintenance: '维护公告'
	};

	const announcementClasses: Record<UpdateAnnouncement['type'], string> = {
		info: 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
		warning: 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
		maintenance: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200'
	};

	const formatPublishedAt = (value: string | null) => {
		if (!value) return '';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return '';
		return new Intl.DateTimeFormat('zh-CN', {
			year: 'numeric',
			month: 'long',
			day: 'numeric'
		}).format(date);
	};

	onMount(async () => {
		const response = await getUpdateAnnouncement(localStorage.token).catch(() => null);
		announcement = response?.announcement ?? null;
		announcementLoading = false;
	});
</script>

<div class="flex h-full flex-col text-sm">
	<div class="mb-4 text-base font-medium">更新</div>

	<VersionUpdatePanel />

	<div class="mb-2 mt-6 flex items-center justify-between gap-3">
		<div class="text-sm font-medium">官方公告</div>
		{#if announcement}
			<div class="flex items-center gap-2 text-[11px] text-gray-400">
				<span class="size-1.5 rounded-full bg-green-500"></span>
				已同步
			</div>
		{/if}
	</div>

	<div class="rounded-lg border border-gray-200 px-5 py-5 dark:border-gray-800">
		{#if announcementLoading}
			<div class="space-y-3" aria-label="正在加载公告">
				<div class="h-5 w-24 animate-pulse rounded bg-gray-100 dark:bg-gray-850"></div>
				<div class="h-4 w-2/5 animate-pulse rounded bg-gray-100 dark:bg-gray-850"></div>
				<div class="h-3 w-full animate-pulse rounded bg-gray-100 dark:bg-gray-850"></div>
			</div>
		{:else if announcement}
			<div class="mb-3 flex flex-wrap items-center gap-2.5">
				<span
					class="inline-flex h-5 items-center rounded-md px-2 text-[10px] font-semibold {announcementClasses[
						announcement.type
					]}"
				>
					{announcementLabels[announcement.type]}
				</span>
				{#if formatPublishedAt(announcement.published_at)}
					<span class="text-[11px] text-gray-400">
						{formatPublishedAt(announcement.published_at)}
					</span>
				{/if}
			</div>
			<div class="text-sm font-semibold leading-6">{announcement.title}</div>
			<div class="mt-2 whitespace-pre-wrap text-xs leading-5 text-gray-600 dark:text-gray-300">
				{announcement.content}
			</div>
		{:else}
			<div class="text-xs text-gray-500 dark:text-gray-400">暂无公告</div>
		{/if}
	</div>
</div>
