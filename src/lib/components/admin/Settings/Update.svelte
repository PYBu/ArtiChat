<script lang="ts">
	import { onMount } from 'svelte';

	import { getUpdateAnnouncement, type UpdateAnnouncement } from '$lib/apis/updates';
	import ArrowRight from '$lib/components/icons/ArrowRight.svelte';
	import AdminSettingField from './AdminSettingField.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import AdminSettingSection from './AdminSettingSection.svelte';
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
	<h2 class="mb-4 text-sm font-medium text-gray-900 dark:text-white">更新</h2>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		<AdminSettingSection title="版本" first>
			<VersionUpdatePanel />
		</AdminSettingSection>

		<AdminSettingSection title="官方公告">
			<AdminSettingRow label="同步状态" description="显示当前部署可用的官方公告。">
				{#if announcementLoading}
					<span class="text-[0.6875rem] text-gray-400">加载中...</span>
				{:else if announcement}
					<span class="flex items-center gap-1.5 text-[0.6875rem] text-gray-500">
						<span class="size-1.5 rounded-full bg-green-500" aria-hidden="true"></span>
						已同步
					</span>
				{:else}
					<span class="text-[0.6875rem] text-gray-400">暂无公告</span>
				{/if}
			</AdminSettingRow>

			<AdminSettingField label="最新公告">
				{#if announcementLoading}
					<div class="space-y-2" aria-label="正在加载公告">
						<div class="h-4 w-24 animate-pulse rounded bg-gray-100 dark:bg-gray-850"></div>
						<div class="h-4 w-2/5 animate-pulse rounded bg-gray-100 dark:bg-gray-850"></div>
						<div class="h-3 w-full animate-pulse rounded bg-gray-100 dark:bg-gray-850"></div>
					</div>
				{:else if announcement}
					<div class="flex flex-col gap-2">
						<div class="flex flex-wrap items-center gap-2">
							<span
								class="inline-flex h-5 items-center rounded-md px-2 text-[0.625rem] font-semibold {announcementClasses[
									announcement.type
								]}"
							>
								{announcementLabels[announcement.type]}
							</span>
							{#if formatPublishedAt(announcement.published_at)}
								<span class="text-[0.6875rem] text-gray-400">
									{formatPublishedAt(announcement.published_at)}
								</span>
							{/if}
						</div>
						<div class="text-sm font-medium leading-5">{announcement.title}</div>
						<div class="whitespace-pre-wrap text-xs leading-5 text-gray-600 dark:text-gray-300">
							{announcement.content}
						</div>
					</div>
				{:else}
					<div class="text-xs text-gray-500 dark:text-gray-400">暂无公告</div>
				{/if}
			</AdminSettingField>
		</AdminSettingSection>

		<AdminSettingSection title="公告管理">
			<AdminSettingRow label="管理公告" description="创建、编辑、启停和删除面向用户的公告。">
				<a
					href="/admin/subscriptions/announcements"
					class="inline-flex h-7 items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 text-[0.6875rem] font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900"
				>
					打开公告管理
					<ArrowRight className="size-3.5" />
				</a>
			</AdminSettingRow>
		</AdminSettingSection>
	</div>
</div>
