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
		body: '',
		display_mode: 'once',
		button_label: '知道了',
		icon: 'sparkles',
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
			form.body = '';
			await load();
		}
		creating = false;
	};

	const save = async (row: Announcement) => {
		const updated = await updateAdminAnnouncement(localStorage.token, row.id, {
			title: row.title,
			body: row.body,
			display_mode: row.display_mode,
			button_label: row.button_label,
			icon: row.icon,
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
		<div class="grid gap-2 md:grid-cols-4">
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">标题</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.title}
				/>
			</label>
			<label class="flex flex-col gap-1">
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
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">Icon</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.icon}
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">按钮文案</span>
				<input
					class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.button_label}
				/>
			</label>
			<label class="flex flex-col gap-1 md:col-span-4">
				<span class="text-xs text-gray-500">内容</span>
				<textarea
					class="min-h-24 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
					bind:value={form.body}
				></textarea>
			</label>
		</div>
		<div class="mt-3 flex justify-end">
			<button
				type="button"
				class="rounded-full bg-black px-3 py-1.5 text-white dark:bg-white dark:text-black"
				disabled={creating || !form.title || !form.body}
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
					<div class="grid gap-2 md:grid-cols-4">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">标题</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.title}
							/>
						</label>
						<label class="flex flex-col gap-1">
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
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">排序</span>
							<input
								type="number"
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.sort_order}
							/>
						</label>
						<label class="flex items-end gap-2 pb-1">
							<input type="checkbox" bind:checked={row.is_active} />
							<span>启用</span>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">Icon</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.icon}
							/>
						</label>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-gray-500">按钮文案</span>
							<input
								class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.button_label}
							/>
						</label>
						<div class="flex items-end text-xs text-gray-500">{modeLabel(row.display_mode)}</div>
						<div class="flex items-end justify-end gap-2">
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
						<label class="flex flex-col gap-1 md:col-span-4">
							<span class="text-xs text-gray-500">内容</span>
							<textarea
								class="min-h-24 rounded-lg border border-gray-100 bg-transparent px-2 py-1 dark:border-gray-850"
								bind:value={row.body}
							></textarea>
						</label>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
