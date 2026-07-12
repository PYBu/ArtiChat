<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Switch from '$lib/components/common/Switch.svelte';
	import { getEmailTemplates, updateEmailTemplate, type EmailTemplate } from '$lib/apis/emails';

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
	let loading = true;
	let saving = false;

	const selectTemplate = (key: string) => {
		selectedKey = key;
		const template = templates.find((item) => item.key === key);
		draft = template ? { ...template, allowed_variables: [...template.allowed_variables] } : null;
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

	const save = async () => {
		if (!draft) return;
		saving = true;
		const updated = await updateEmailTemplate(localStorage.token, draft.key, {
			subject: draft.subject,
			markdown_body: draft.markdown_body,
			is_enabled: draft.is_enabled
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (updated) {
			templates = templates.map((item) => (item.key === updated.key ? updated : item));
			selectTemplate(updated.key);
			toast.success('邮件模板已保存。');
		}
		saving = false;
	};

	onMount(load);
</script>

{#if loading}
	<div class="py-8 text-sm text-gray-500">加载中...</div>
{:else if draft}
	<div class="flex max-w-4xl flex-col gap-5">
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
		<label class="flex flex-col gap-1">
			<span class="text-xs text-gray-500">Markdown 正文</span>
			<textarea
				rows="14"
				class="min-h-64 rounded-lg border border-gray-100 bg-transparent px-3 py-2 font-mono text-sm dark:border-gray-850"
				bind:value={draft.markdown_body}
			></textarea>
		</label>
		<div>
			<div class="mb-2 text-xs text-gray-500">可用变量</div>
			<div class="flex flex-wrap gap-2">
				{#each draft.allowed_variables as variable}
					<code class="rounded border border-gray-200 px-2 py-1 text-xs dark:border-gray-800"
						>{'{{'}{variable}{'}}'}</code
					>
				{/each}
			</div>
		</div>
		<div class="flex justify-end">
			<button
				type="button"
				class="rounded-lg bg-black px-4 py-2 text-sm text-white disabled:opacity-50 dark:bg-white dark:text-black"
				disabled={saving}
				on:click={save}>{saving ? '保存中...' : '保存模板'}</button
			>
		</div>
	</div>
{:else}
	<div class="py-8 text-sm text-gray-500">暂无邮件模板。</div>
{/if}
