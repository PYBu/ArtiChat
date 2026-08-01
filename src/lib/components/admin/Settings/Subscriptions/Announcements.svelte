<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Modal from '$lib/components/common/Modal.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import {
		createAdminAnnouncement,
		deleteAdminAnnouncement,
		getAdminAnnouncements,
		updateAdminAnnouncement,
		type Announcement,
		type AnnouncementInput
	} from '$lib/apis/announcements';

	const DEFAULT_IMAGE_URL =
		'https://github.com/PYBu/ArtiChat/blob/main/artivis-ass/title.png?raw=true';

	let rows: Announcement[] = [];
	let loading = true;
	let creating = false;
	let editing = false;
	let savingEdit = false;
	let draft: Announcement | null = null;
	let savingIds = new Set<string>();

	const newForm = (): AnnouncementInput => ({
		title: '',
		summary: '',
		body: '',
		image_url: DEFAULT_IMAGE_URL,
		view_button_label: '查看公告',
		close_button_label: '关闭',
		display_mode: 'once',
		is_active: true
	});

	let form: AnnouncementInput = newForm();

	const modeLabel = (mode?: string) => {
		if (mode === 'once') return '弹出一次';
		if (mode === 'every_login') return '每次登录';
		if (mode === 'new_user') return '新用户';
		return mode ?? '-';
	};

	const load = async () => {
		loading = true;
		const response = await getAdminAnnouncements(localStorage.token, true).catch((error) => {
			toast.error(`${error}`);
			return { items: [] };
		});
		rows = response?.items ?? [];
		loading = false;
	};

	const create = async () => {
		creating = true;
		const created = await createAdminAnnouncement(localStorage.token, form).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (created) {
			toast.success('公告已创建。');
			form = newForm();
			await load();
		}
		creating = false;
	};

	const toggleActive = async (row: Announcement, nextState: boolean) => {
		if (savingIds.has(row.id)) return;
		const previousState = row.is_active;
		row.is_active = nextState;
		rows = [...rows];
		savingIds = new Set([...savingIds, row.id]);
		const updated = await updateAdminAnnouncement(localStorage.token, row.id, {
			is_active: nextState
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (updated) Object.assign(row, updated);
		else row.is_active = previousState;
		rows = [...rows];
		const nextSavingIds = new Set(savingIds);
		nextSavingIds.delete(row.id);
		savingIds = nextSavingIds;
	};

	const openEdit = (row: Announcement) => {
		draft = { ...row };
		editing = true;
	};

	const closeEdit = () => {
		if (savingEdit) return;
		draft = null;
		editing = false;
	};

	const saveEdit = async () => {
		if (!draft || savingEdit) return;
		savingEdit = true;
		const updated = await updateAdminAnnouncement(localStorage.token, draft.id, {
			title: draft.title,
			summary: draft.summary,
			body: draft.body,
			image_url: draft.image_url,
			view_button_label: draft.view_button_label,
			close_button_label: draft.close_button_label,
			display_mode: draft.display_mode,
			is_active: draft.is_active,
			sort_order: Number(draft.sort_order ?? 0)
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (updated) {
			const index = rows.findIndex((row) => row.id === updated.id);
			if (index >= 0) rows[index] = updated;
			rows = [...rows];
			toast.success('公告已保存。');
			closeEdit();
		}
		savingEdit = false;
	};

	const remove = async (row: Announcement) => {
		if (!window.confirm(`永久删除“${row.title}”及其查看记录？此操作不可恢复。`)) return;
		const deleted = await deleteAdminAnnouncement(localStorage.token, row.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (deleted?.deleted) {
			rows = rows.filter((item) => item.id !== row.id);
			toast.success('公告已永久删除。');
		}
	};

	onMount(load);
</script>

<div class="admin-operations flex flex-col gap-4">
	<div>
		<div class="text-base font-medium">公告</div>
		<div class="text-xs text-gray-500">创建登录公告，独立控制启停并保留实时预览。</div>
	</div>

	<div class="grid gap-3 lg:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.75fr)]">
		<div
			class="rounded-lg border border-gray-100/60 bg-white/40 p-3 dark:border-white/[0.06] dark:bg-white/[0.02]"
		>
			<div class="mb-3 text-sm font-medium">创建公告</div>
			<div class="grid gap-3 md:grid-cols-2">
				<label class="flex min-w-0 flex-col gap-1 md:col-span-2"
					><span class="text-xs text-gray-500">标题</span><input
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.title}
					/></label
				>
				<label class="flex min-w-0 flex-col gap-1"
					><span class="text-xs text-gray-500">弹出规则</span><select
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.display_mode}
						><option value="once">弹出一次</option><option value="every_login">每次登录</option
						><option value="new_user">新用户</option></select
					></label
				>
				<label class="flex min-w-0 flex-col gap-1"
					><span class="text-xs text-gray-500">封面图片地址</span><input
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.image_url}
					/></label
				>
				<label class="flex min-w-0 flex-col gap-1 md:col-span-2"
					><span class="text-xs text-gray-500">摘要</span><textarea
						class="min-h-16 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 py-1 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.summary}
					></textarea></label
				>
				<label class="flex min-w-0 flex-col gap-1"
					><span class="text-xs text-gray-500">查看按钮文案</span><input
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.view_button_label}
					/></label
				>
				<label class="flex min-w-0 flex-col gap-1"
					><span class="text-xs text-gray-500">关闭按钮文案</span><input
						class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.close_button_label}
					/></label
				>
				<label class="flex min-w-0 flex-col gap-1 md:col-span-2"
					><span class="text-xs text-gray-500">展开内容</span><textarea
						class="min-h-28 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 py-1 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
						bind:value={form.body}
					></textarea></label
				>
			</div>
			<div class="mt-3 flex justify-end">
				<button
					type="button"
					class="rounded-lg bg-black px-3 py-1.5 text-xs font-medium text-white transition hover:bg-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black"
					disabled={creating ||
						!form.title ||
						!form.summary ||
						!form.body ||
						!form.view_button_label ||
						!form.close_button_label}
					on:click={create}>{creating ? '创建中...' : '创建公告'}</button
				>
			</div>
		</div>

		<div class="min-w-0">
			<div class="mb-1 text-[11px] font-medium text-gray-500">实时预览</div>
			<div
				class="overflow-hidden rounded-lg border border-gray-100/60 bg-white/40 dark:border-white/[0.06] dark:bg-white/[0.02]"
			>
				{#if form.image_url}<img
						class="h-32 w-full object-cover"
						src={form.image_url}
						alt="公告封面预览"
					/>{/if}
				<div class="p-3">
					<div class="text-sm font-medium text-gray-900 dark:text-white">
						{form.title || '未命名公告'}
					</div>
					<div class="mt-1 text-[11px] leading-4 text-gray-500">
						{form.summary || '公告摘要将在这里显示。'}
					</div>
					<div class="mt-3 flex justify-end gap-2">
						<button type="button" class="rounded-lg px-2.5 py-1.5 text-xs text-gray-500"
							>{form.close_button_label || '关闭'}</button
						><button
							type="button"
							class="rounded-lg bg-black px-2.5 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-black"
							>{form.view_button_label || '查看公告'}</button
						>
					</div>
				</div>
			</div>
		</div>
	</div>

	<div>
		<div class="mb-2 flex items-end justify-between gap-3">
			<div>
				<div class="text-sm font-medium">现有公告</div>
				<div class="text-[11px] text-gray-500">启用和停用公告统一显示，状态可独立切换。</div>
			</div>
			<span class="text-[11px] text-gray-400">{rows.length} 条</span>
		</div>
		{#if loading}
			<div class="text-gray-500">加载中...</div>
		{:else if rows.length === 0}
			<div
				class="rounded-lg border border-gray-100/60 bg-gray-50/30 p-3 text-xs text-gray-500 dark:border-white/[0.06] dark:bg-white/[0.02]"
			>
				暂无公告。
			</div>
		{:else}
			<div class="grid gap-2">
				{#each rows as row (row.id)}
					<div
						class="grid gap-3 rounded-lg border border-gray-100/60 bg-white/40 p-3 dark:border-white/[0.06] dark:bg-white/[0.02] md:grid-cols-[6rem_minmax(0,1fr)_auto] md:items-center"
					>
						{#if row.image_url}<img
								class="h-16 w-full rounded-md object-cover md:h-16"
								src={row.image_url}
								alt=""
							/>{:else}<div class="h-16 rounded-md bg-gray-50 dark:bg-white/[0.04]"></div>{/if}
						<div class="min-w-0">
							<div class="truncate text-sm font-medium">{row.title}</div>
							<div class="mt-1 line-clamp-2 text-xs text-gray-500">{row.summary}</div>
							<div class="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-400">
								<span class:font-medium={row.is_active} class:text-green-600={row.is_active}
									>{row.is_active ? '启用' : '已停用'}</span
								><span>{modeLabel(row.display_mode)}</span><span>排序 {row.sort_order}</span>
							</div>
						</div>
						<div class="flex items-center justify-end gap-1">
							<Switch
								state={row.is_active}
								disabled={savingIds.has(row.id)}
								ariaLabel={`${row.is_active ? '停用' : '启用'} ${row.title}`}
								on:change={(event) => toggleActive(row, event.detail)}
							/><button
								type="button"
								class="rounded-lg px-2.5 py-1.5 text-xs text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-white/[0.05]"
								on:click={() => openEdit(row)}>编辑</button
							><button
								type="button"
								class="rounded-lg px-2.5 py-1.5 text-xs text-red-600 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-950/30"
								on:click={() => remove(row)}>删除</button
							>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<Modal
	bind:show={editing}
	size="lg"
	closeOnBackdrop={false}
	closeOnEscape={false}
	className="rounded-lg bg-white dark:bg-gray-900"
>
	{#if draft}
		<div class="flex max-h-[85vh] flex-col">
			<div
				class="flex items-start justify-between border-b border-gray-100/70 p-4 dark:border-white/[0.06]"
			>
				<div>
					<div class="text-sm font-medium">编辑公告</div>
					<div class="mt-1 text-[11px] text-gray-500">保存后立即更新公告内容和状态。</div>
				</div>
				<button
					type="button"
					class="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 dark:hover:bg-white/[0.06]"
					aria-label="关闭"
					on:click={closeEdit}><XMark className="size-4" strokeWidth="2" /></button
				>
			</div>
			<div class="min-h-0 overflow-y-auto p-4">
				<div class="grid gap-3 md:grid-cols-2">
					<label class="flex flex-col gap-1 md:col-span-2"
						><span class="text-xs text-gray-500">标题</span><input
							class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
							bind:value={draft.title}
						/></label
					><label class="flex flex-col gap-1"
						><span class="text-xs text-gray-500">弹出规则</span><select
							class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
							bind:value={draft.display_mode}
							><option value="once">弹出一次</option><option value="every_login">每次登录</option
							><option value="new_user">新用户</option></select
						></label
					><label class="flex flex-col gap-1"
						><span class="text-xs text-gray-500">排序</span><input
							type="number"
							class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
							bind:value={draft.sort_order}
						/></label
					><label class="flex flex-col gap-1 md:col-span-2"
						><span class="text-xs text-gray-500">封面图片地址</span><input
							class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
							bind:value={draft.image_url}
						/></label
					><label class="flex flex-col gap-1 md:col-span-2"
						><span class="text-xs text-gray-500">摘要</span><textarea
							class="min-h-16 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 py-1 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
							bind:value={draft.summary}
						></textarea></label
					><label class="flex flex-col gap-1"
						><span class="text-xs text-gray-500">查看按钮文案</span><input
							class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
							bind:value={draft.view_button_label}
						/></label
					><label class="flex flex-col gap-1"
						><span class="text-xs text-gray-500">关闭按钮文案</span><input
							class="h-7 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
							bind:value={draft.close_button_label}
						/></label
					><label class="flex flex-col gap-1 md:col-span-2"
						><span class="text-xs text-gray-500">展开内容</span><textarea
							class="min-h-32 rounded-lg border border-gray-100/60 bg-gray-50/40 px-2 py-1 text-xs text-gray-700 outline-hidden focus:border-blue-400 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-gray-300"
							bind:value={draft.body}
						></textarea></label
					><label class="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300"
						><input type="checkbox" bind:checked={draft.is_active} />启用公告</label
					>
				</div>
			</div>
			<div class="flex justify-end gap-2 border-t border-gray-100/70 p-4 dark:border-white/[0.06]">
				<button
					type="button"
					class="rounded-lg border border-gray-200/70 px-3 py-1.5 text-xs text-gray-600 dark:border-white/[0.08] dark:text-gray-300"
					disabled={savingEdit}
					on:click={closeEdit}>取消</button
				><button
					type="button"
					class="rounded-lg bg-black px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black"
					disabled={savingEdit || !draft.title || !draft.body}
					on:click={saveEdit}>{savingEdit ? '保存中...' : '保存修改'}</button
				>
			</div>
		</div>
	{/if}
</Modal>

<style>
	.admin-operations :global(.text-base.font-medium) {
		font-size: 0.875rem;
		line-height: 1.25rem;
	}

	.admin-operations :global(.text-xs.text-gray-500) {
		font-size: 0.6875rem;
		line-height: 1rem;
	}
</style>
