<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import AdminSettingField from '$lib/components/admin/Settings/AdminSettingField.svelte';
	import AdminSettingRow from '$lib/components/admin/Settings/AdminSettingRow.svelte';
	import AdminSettingSection from '$lib/components/admin/Settings/AdminSettingSection.svelte';
	import SettingsSelect from '$lib/components/common/SettingsSelect.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Code from '$lib/components/icons/Code.svelte';
	import DocumentCheck from '$lib/components/icons/DocumentCheck.svelte';
	import Eye from '$lib/components/icons/Eye.svelte';
	import Refresh from '$lib/components/icons/Refresh.svelte';
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

	const inputClass =
		'w-full max-w-xl h-7 rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';
	const actionButtonClass =
		'text-xs text-gray-500 transition-colors hover:text-gray-900 disabled:opacity-50 dark:text-gray-500 dark:hover:text-white';
	const primaryButtonClass =
		'flex h-7 items-center gap-2 rounded-lg bg-black px-3 text-xs font-medium text-white transition hover:bg-gray-800 disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-gray-200';

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
	<div class="flex w-full flex-col">
		<AdminSettingSection title="模板" first>
			<AdminSettingRow label="邮件类型" description="选择要编辑的系统邮件模板。">
				<SettingsSelect
					bind:value={selectedKey}
					className="w-56 max-w-full"
					on:change={() => selectTemplate(selectedKey)}
				>
					{#each templates as template}
						<option value={template.key}>{labels[template.key] ?? template.key}</option>
					{/each}
				</SettingsSelect>
			</AdminSettingRow>
			<AdminSettingRow
				label={labels[draft.key] ?? draft.key}
				description="关闭后，该类邮件不会由系统自动发送。"
			>
				<Switch bind:state={draft.is_enabled} ariaLabel="启用此邮件模板" />
			</AdminSettingRow>
		</AdminSettingSection>

		<AdminSettingSection title="内容">
			<AdminSettingField label="主题">
				<input class={inputClass} bind:value={draft.subject} />
			</AdminSettingField>

			<AdminSettingRow label="编辑模式" description="在 HTML 源文和渲染预览之间切换。">
				<div class="flex items-center gap-2">
					<div
						class="inline-flex rounded-lg border border-gray-100/50 p-0.5 dark:border-white/[0.04]"
					>
						<button
							type="button"
							class="flex h-7 items-center gap-1.5 rounded-md px-2.5 text-xs {mode === 'html'
								? 'bg-gray-100 font-medium dark:bg-gray-800'
								: 'text-gray-500'}"
							on:click={() => setMode('html')}
						>
							<Code className="size-3.5" />
							HTML
						</button>
						<button
							type="button"
							class="flex h-7 items-center gap-1.5 rounded-md px-2.5 text-xs {mode === 'preview'
								? 'bg-gray-100 font-medium dark:bg-gray-800'
								: 'text-gray-500'}"
							on:click={() => setMode('preview')}
						>
							<Eye className="size-3.5" />
							预览
						</button>
					</div>

					{#if mode === 'preview'}
						<button
							type="button"
							title="刷新预览"
							aria-label="刷新预览"
							class="flex size-7 items-center justify-center rounded-lg border border-gray-100/50 text-gray-500 disabled:opacity-50 dark:border-white/[0.04]"
							disabled={previewing}
							on:click={loadPreview}
						>
							<Refresh className="size-3.5 {previewing ? 'animate-spin' : ''}" />
						</button>
					{/if}
				</div>
			</AdminSettingRow>

			{#if mode === 'html'}
				<AdminSettingField
					label="HTML 正文"
					description="支持模板变量；请保持 HTML 可被邮件客户端渲染。"
				>
					<textarea
						rows="20"
						class="min-h-[32rem] w-full resize-y rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 font-mono text-xs leading-5 text-gray-700 outline-hidden transition-colors focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500"
						bind:value={draft.html_body}
					></textarea>
				</AdminSettingField>
			{:else}
				<AdminSettingField label="HTML 预览">
					<div
						class="min-h-[36rem] overflow-hidden rounded-lg border border-gray-100/50 bg-white dark:border-white/[0.04]"
					>
						{#if previewing}
							<div class="flex min-h-[36rem] items-center justify-center text-sm text-gray-500">
								加载预览...
							</div>
						{:else if preview}
							<div class="border-b border-gray-100 px-3 py-2 text-xs dark:border-gray-850">
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
				</AdminSettingField>
			{/if}
		</AdminSettingSection>

		<AdminSettingSection title="变量">
			<AdminSettingField label="可用变量" description="点击变量即可追加到 HTML 正文末尾。">
				<div class="flex max-w-xl flex-wrap gap-1.5">
					{#each draft.allowed_variables as variable}
						<button
							type="button"
							class="rounded-md border border-gray-100/50 px-2 py-1 font-mono text-[0.6875rem] text-gray-500 transition-colors hover:border-gray-300 hover:text-gray-900 dark:border-white/[0.04] dark:hover:border-white/20 dark:hover:text-white"
							on:click={() => insertVariable(variable)}
						>
							{'{{'}{variable}{'}}'}
						</button>
					{/each}
				</div>
			</AdminSettingField>
		</AdminSettingSection>

		<div class="mt-5 flex justify-end">
			<button type="button" class={primaryButtonClass} disabled={saving} on:click={save}>
				<DocumentCheck className="size-3.5" />
				{saving ? '保存中...' : '保存模板'}
			</button>
		</div>
	</div>
{:else}
	<div class="py-8 text-sm text-gray-500">暂无邮件模板。</div>
{/if}
