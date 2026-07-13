<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Code from '$lib/components/icons/Code.svelte';
	import DocumentCheck from '$lib/components/icons/DocumentCheck.svelte';
	import Eye from '$lib/components/icons/Eye.svelte';
	import Refresh from '$lib/components/icons/Refresh.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import {
		getEmailTemplates,
		previewEmailTemplate,
		updateEmailTemplate,
		type EmailTemplate,
		type EmailTemplatePreview
	} from '$lib/apis/emails';

	const labels: Record<string, string> = {
		registration_code: '注册验证码',
		login_code: '登录验证码',
		sensitive_action_code: '敏感操作验证码',
		password_reset: '找回密码',
		password_changed: '密码修改通知',
		email_changed: '登录邮箱修改通知',
		billing_address_changed: '付款信息修改通知',
		subscription_changed: '订阅变更通知',
		smtp_test: 'SMTP 测试邮件'
	};

	let templates: EmailTemplate[] = [];
	let selectedKey = '';
	let draft: EmailTemplate | null = null;
	let preview: EmailTemplatePreview | null = null;
	let mode: 'html' | 'preview' = 'html';
	let loading = true;
	let saving = false;
	let previewing = false;
	let previewController: AbortController | null = null;
	let previewRequest = 0;

	const cancelPreview = () => {
		previewRequest += 1;
		previewController?.abort();
		previewController = null;
		previewing = false;
	};

	const selectTemplate = (key: string) => {
		cancelPreview();
		selectedKey = key;
		const template = templates.find((item) => item.key === key);
		draft = template ? { ...template, allowed_variables: [...template.allowed_variables] } : null;
		preview = null;
		mode = 'html';
	};

	const load = async () => {
		loading = true;
		templates = await getEmailTemplates(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return [];
		});
		if (templates.length) selectTemplate(templates[0].key);
		loading = false;
	};

	const loadPreview = async () => {
		if (!draft) return;
		previewController?.abort();
		const controller = new AbortController();
		previewController = controller;
		const request = ++previewRequest;
		const currentDraft = draft;
		previewing = true;
		try {
			const result = await previewEmailTemplate(
				localStorage.token,
				currentDraft.key,
				{
					subject: currentDraft.subject,
					html_body: currentDraft.html_body,
					is_enabled: currentDraft.is_enabled
				},
				controller.signal
			);
			if (request === previewRequest) preview = result;
		} catch (error) {
			if (!(error instanceof Error && error.name === 'AbortError') && request === previewRequest) {
				toast.error(`${error}`);
				preview = null;
			}
		} finally {
			if (request === previewRequest) {
				previewController = null;
				previewing = false;
			}
		}
	};

	const setMode = async (nextMode: 'html' | 'preview') => {
		mode = nextMode;
		if (nextMode === 'preview') await loadPreview();
	};

	const insertVariable = (variable: string) => {
		if (!draft) return;
		draft.html_body = `${draft.html_body}${draft.html_body ? '\n' : ''}{{${variable}}}`;
		mode = 'html';
	};

	const save = async () => {
		if (!draft) return;
		saving = true;
		const updated = await updateEmailTemplate(localStorage.token, draft.key, {
			subject: draft.subject,
			html_body: draft.html_body,
			is_enabled: draft.is_enabled
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (updated) {
			templates = templates.map((item) => (item.key === updated.key ? updated : item));
			const currentMode = mode;
			selectTemplate(updated.key);
			mode = currentMode;
			if (mode === 'preview') await loadPreview();
			toast.success('邮件模板已保存。');
		}
		saving = false;
	};

	onMount(load);
	onDestroy(cancelPreview);
</script>

{#if loading}
	<div class="py-8 text-sm text-gray-500">加载中...</div>
{:else if draft}
	<div class="flex max-w-5xl flex-col gap-5">
		<label class="flex flex-col gap-1">
			<span class="text-xs text-gray-500">邮件类型</span>
			<select
				class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
				bind:value={selectedKey}
				on:change={() => selectTemplate(selectedKey)}
			>
				{#each templates as template}
					<option value={template.key}>{labels[template.key] ?? template.key}</option>
				{/each}
			</select>
		</label>

		<div
			class="flex items-center justify-between gap-4 border-b border-gray-100 pb-4 dark:border-gray-850"
		>
			<div class="font-medium">{labels[draft.key] ?? draft.key}</div>
			<Switch bind:state={draft.is_enabled} ariaLabel="启用此邮件模板" />
		</div>

		<label class="flex flex-col gap-1">
			<span class="text-xs text-gray-500">主题</span>
			<input
				class="rounded-lg border border-gray-100 bg-transparent px-3 py-2 dark:border-gray-850"
				bind:value={draft.subject}
			/>
		</label>

		<div class="flex items-center justify-between gap-3">
			<div class="inline-flex rounded-md border border-gray-200 p-0.5 dark:border-gray-800">
				<button
					type="button"
					class="flex h-8 items-center gap-1.5 rounded px-3 text-xs {mode === 'html'
						? 'bg-gray-100 font-medium dark:bg-gray-800'
						: 'text-gray-500'}"
					on:click={() => setMode('html')}
				>
					<Code className="size-4" />
					HTML
				</button>
				<button
					type="button"
					class="flex h-8 items-center gap-1.5 rounded px-3 text-xs {mode === 'preview'
						? 'bg-gray-100 font-medium dark:bg-gray-800'
						: 'text-gray-500'}"
					on:click={() => setMode('preview')}
				>
					<Eye className="size-4" />
					预览
				</button>
			</div>

			{#if mode === 'preview'}
				<button
					type="button"
					title="刷新预览"
					aria-label="刷新预览"
					class="flex size-8 items-center justify-center rounded-md border border-gray-200 text-gray-600 disabled:opacity-50 dark:border-gray-800 dark:text-gray-300"
					disabled={previewing}
					on:click={loadPreview}
				>
					<Refresh className="size-4 {previewing ? 'animate-spin' : ''}" />
				</button>
			{/if}
		</div>

		{#if mode === 'html'}
			<label class="flex flex-col gap-1">
				<span class="text-xs text-gray-500">HTML 正文</span>
				<textarea
					rows="20"
					class="min-h-[32rem] w-full resize-y rounded-lg border border-gray-100 bg-transparent px-3 py-2 font-mono text-sm leading-6 dark:border-gray-850"
					bind:value={draft.html_body}
				></textarea>
			</label>
		{:else}
			<div
				class="min-h-[36rem] overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800"
			>
				{#if previewing}
					<div class="flex min-h-[36rem] items-center justify-center text-sm text-gray-500">
						加载预览...
					</div>
				{:else if preview}
					<div class="border-b border-gray-200 px-4 py-3 text-sm dark:border-gray-800">
						<span class="text-gray-500">主题：</span>{preview.subject}
					</div>
					<iframe
						title="邮件 HTML 预览"
						sandbox=""
						srcdoc={preview.html_body}
						class="h-[34rem] w-full bg-white"
					></iframe>
				{:else}
					<div class="flex min-h-[36rem] items-center justify-center text-sm text-gray-500">
						预览不可用
					</div>
				{/if}
			</div>
		{/if}

		<div>
			<div class="mb-2 text-xs text-gray-500">可用变量</div>
			<div class="flex flex-wrap gap-2">
				{#each draft.allowed_variables as variable}
					<button
						type="button"
						class="rounded border border-gray-200 px-2 py-1 font-mono text-xs hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-900"
						on:click={() => insertVariable(variable)}
					>
						{'{{'}{variable}{'}}'}
					</button>
				{/each}
			</div>
		</div>

		<div class="flex justify-end">
			<button
				type="button"
				class="flex items-center gap-2 rounded-lg bg-black px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-black"
				disabled={saving}
				on:click={save}
			>
				<DocumentCheck className="size-4" />
				{saving ? '保存中...' : '保存模板'}
			</button>
		</div>
	</div>
{:else}
	<div class="py-8 text-sm text-gray-500">暂无邮件模板。</div>
{/if}
