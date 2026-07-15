<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		createAdminAnnouncement,
		deleteAdminAnnouncement,
		getAdminAnnouncements,
		updateAdminAnnouncement,
		type Announcement,
		type AnnouncementInput
	} from '$lib/apis/announcements';

	let rows: Announcement[] = [];
	let loading = true;
	let creating = false;
	let showInactive = false;
	let form: AnnouncementInput = {
		title: '',
		summary: '',
		body: '',
		image_url: '/assets/images/space.jpg',
		view_button_label: '查看公告',
		close_button_label: '关闭',
		display_mode: 'once',
		is_active: true
	};

	const modeLabel = (mode?: string) => {
		if (mode === 'once') return '弹出一次';
		if (mode === 'every_login') return '每次登录';
		if (mode === 'new_user') return '新用户';
		return mode ?? '-';
	};

	const load = async () => {
		loading = true;
		const response = await getAdminAnnouncements(localStorage.token, showInactive).catch(
			(error) => {
				toast.error(`${error}`);
				return { items: [] };
			}
		);
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
			form.title = '';
			form.summary = '';
			form.body = '';
			await load();
		}
		creating = false;
	};

	const save = async (row: Announcement) => {
		const updated = await updateAdminAnnouncement(localStorage.token, row.id, {
			title: row.title,
			summary: row.summary,
			body: row.body,
			image_url: row.image_url,
			view_button_label: row.view_button_label,
			close_button_label: row.close_button_label,
			display_mode: row.display_mode,
			is_active: row.is_active,
			sort_order: Number(row.sort_order ?? 0)
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (updated) {
			Object.assign(row, updated);
			toast.success('公告已保存。');
		}
	};

	const remove = async (row: Announcement) => {
		const deleted = await deleteAdminAnnouncement(localStorage.token, row.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (deleted) {
			toast.success('公告已删除。');
			await load();
		}
	};

	onMount(load);
</script>

<div class="flex flex-col gap-4">
	<div class="flex flex-wrap items-start justify-between gap-2">
		<div>
			<div class="text-base font-medium">公告</div>
			<div class="text-xs text-gray-500">
				创建登录后弹出的公告，可设置弹出一次、每次登录或仅新用户弹出。
			</div>
		</div>
		<label class="flex items-center gap-2 text-xs text-gray-500">
			<input type="checkbox" bind:checked={showInactive} on:change={() => load()} />
			<span>显示已停用</span>
		</label>
	</div>

	<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
		<div class="grid gap-3 md:grid-cols-2">
			<label class="flex min-w-0 flex-col gap-1">
				<span class="text-xs text-gray-500">标题</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.title}
				/>
			</label>
			<label class="flex min-w-0 flex-col gap-1">
				<span class="text-xs text-gray-500">弹出规则</span>
				<select
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.display_mode}
				>
					<option value="once">弹出一次</option>
					<option value="every_login">每次登录</option>
					<option value="new_user">新用户</option>
				</select>
			</label>
			<label class="flex min-w-0 flex-col gap-1 md:col-span-2">
				<span class="text-xs text-gray-500">摘要</span>
				<textarea
					class="min-h-20 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.summary}
				></textarea>
			</label>
			<label class="flex min-w-0 flex-col gap-1 md:col-span-2">
				<span class="text-xs text-gray-500">封面图片地址</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.image_url}
				/>
			</label>
			<label class="flex min-w-0 flex-col gap-1">
				<span class="text-xs text-gray-500">查看按钮文案</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.view_button_label}
				/>
			</label>
			<label class="flex min-w-0 flex-col gap-1">
				<span class="text-xs text-gray-500">关闭按钮文案</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.close_button_label}
				/>
			</label>
			<label class="flex min-w-0 flex-col gap-1 md:col-span-2">
				<span class="text-xs text-gray-500">展开内容</span>
				<textarea
					class="min-h-36 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.body}
				></textarea>
			</label>
		</div>
		<div class="mt-3 flex justify-end">
			<button
				type="button"
				class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black"
				disabled={creating ||
					!form.title ||
					!form.summary ||
					!form.body ||
					!form.view_button_label ||
					!form.close_button_label}
				on:click={create}
			>
				{creating ? '创建中' : '创建公告'}
			</button>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500">加载中...</div>
	{:else if rows.length === 0}
		<div class="rounded-lg border border-gray-100 p-3 text-gray-500 dark:border-gray-850">
			暂无公告。
		</div>
	{:else}
		<div class="flex flex-col gap-2">
			{#each rows as row (row.id)}
				<div class="rounded-lg border border-gray-100 p-3 dark:border-gray-850">
					<div class="grid gap-3 md:grid-cols-2">
						<label class="flex min-w-0 flex-col gap-1">
							<span class="text-xs text-gray-500">标题</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.title}
							/>
						</label>
						<label class="flex min-w-0 flex-col gap-1">
							<span class="text-xs text-gray-500">弹出规则</span>
							<select
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.display_mode}
							>
								<option value="once">弹出一次</option>
								<option value="every_login">每次登录</option>
								<option value="new_user">新用户</option>
							</select>
						</label>
						<label class="flex min-w-0 flex-col gap-1">
							<span class="text-xs text-gray-500">排序</span>
							<input
								type="number"
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.sort_order}
							/>
						</label>
						<label class="flex min-w-0 items-end gap-2 pb-1">
							<input type="checkbox" bind:checked={row.is_active} />
							<span>启用</span>
						</label>
						<label class="flex min-w-0 flex-col gap-1 md:col-span-2">
							<span class="text-xs text-gray-500">摘要</span>
							<textarea
								class="min-h-20 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.summary}
							></textarea>
						</label>
						<label class="flex min-w-0 flex-col gap-1 md:col-span-2">
							<span class="text-xs text-gray-500">封面图片地址</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.image_url}
							/>
						</label>
						<label class="flex min-w-0 flex-col gap-1">
							<span class="text-xs text-gray-500">查看按钮文案</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.view_button_label}
							/>
						</label>
						<label class="flex min-w-0 flex-col gap-1">
							<span class="text-xs text-gray-500">关闭按钮文案</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.close_button_label}
							/>
						</label>
						<label class="flex min-w-0 flex-col gap-1 md:col-span-2">
							<span class="text-xs text-gray-500">展开内容</span>
							<textarea
								class="min-h-36 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.body}
							></textarea>
						</label>
						<div class="flex items-end text-xs text-gray-500">{modeLabel(row.display_mode)}</div>
						<div class="flex flex-wrap items-end justify-end gap-2">
							<button
								type="button"
								class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black"
								on:click={() => save(row)}
							>
								保存
							</button>
							<button
								type="button"
								class="rounded-full px-3 py-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
								on:click={() => remove(row)}
							>
								删除
							</button>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
