<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { getEmailDeliveries, retryEmailDelivery, type EmailDelivery } from '$lib/apis/emails';

	const templateLabels: Record<string, string> = {
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
	const statusLabels: Record<string, string> = {
		pending: '等待发送',
		sending: '发送中',
		sent: '已发送',
		failed: '失败'
	};

	let deliveries: EmailDelivery[] = [];
	let loading = true;
	let retryingId = '';

	const formatDate = (value: number | null) =>
		value ? new Date(value * 1000).toLocaleString() : '-';

	const load = async () => {
		loading = true;
		deliveries = await getEmailDeliveries(localStorage.token, { limit: 100 }).catch((error) => {
			toast.error(`${error}`);
			return [];
		});
		loading = false;
	};

	const retry = async (deliveryId: string) => {
		retryingId = deliveryId;
		const updated = await retryEmailDelivery(localStorage.token, deliveryId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (updated) {
			deliveries = deliveries.map((item) => (item.id === updated.id ? updated : item));
			if (updated.status === 'sent') toast.success('邮件已重新发送。');
			else toast.error(updated.error ?? '邮件重试失败。');
		}
		retryingId = '';
	};

	onMount(load);
</script>

<div class="flex flex-col gap-4">
	<div class="flex justify-end">
		<button
			type="button"
			class="rounded-lg border border-gray-200 px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50 dark:border-gray-800 dark:hover:bg-gray-900"
			disabled={loading}
			on:click={load}>刷新</button
		>
	</div>
	{#if loading}
		<div class="py-8 text-sm text-gray-500">加载中...</div>
	{:else if deliveries.length === 0}
		<div
			class="border-y border-gray-100 py-8 text-center text-sm text-gray-500 dark:border-gray-850"
		>
			暂无发送记录。
		</div>
	{:else}
		<div
			class="divide-y divide-gray-100 border-y border-gray-100 dark:divide-gray-850 dark:border-gray-850"
		>
			{#each deliveries as delivery}
				<div
					class="grid gap-3 py-4 text-sm md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_7rem_10rem_auto] md:items-center"
				>
					<div class="min-w-0">
						<div class="truncate font-medium">{delivery.subject}</div>
						<div class="mt-1 truncate text-xs text-gray-500">{delivery.recipient}</div>
					</div>
					<div class="text-xs text-gray-500">
						{templateLabels[delivery.template_key] ?? delivery.template_key}
					</div>
					<div>
						<span
							class={delivery.status === 'sent'
								? 'text-green-700 dark:text-green-400'
								: delivery.status === 'failed'
									? 'text-red-600'
									: 'text-gray-500'}>{statusLabels[delivery.status] ?? delivery.status}</span
						>
						<div class="mt-1 text-xs text-gray-500">尝试 {delivery.attempts} 次</div>
					</div>
					<div class="text-xs text-gray-500">
						{formatDate(delivery.sent_at ?? delivery.created_at)}
					</div>
					<div class="flex justify-end">
						{#if delivery.status === 'failed'}
							<button
								type="button"
								class="rounded-lg border border-gray-200 px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-50 dark:border-gray-800 dark:hover:bg-gray-900"
								disabled={retryingId === delivery.id}
								on:click={() => retry(delivery.id)}
								>{retryingId === delivery.id ? '重试中...' : '重试'}</button
							>
						{/if}
					</div>
					{#if delivery.error}
						<div class="text-xs text-red-600 md:col-span-5">{delivery.error}</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
