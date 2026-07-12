<script lang="ts">
	export let title: string;
	export let description: string;
</script>

<div class="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6">
	<div class="flex items-start gap-3 border-b border-gray-100 pb-3 dark:border-gray-850">
		<a
			href="/admin/subscriptions"
			class="mt-0.5 inline-flex size-8 flex-none items-center justify-center rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850"
			aria-label="返回订阅运营"
			title="返回订阅运营"
		>
			<span aria-hidden="true">←</span>
		</a>
		<div class="min-w-0">
			<h1 class="text-lg font-medium">{title}</h1>
			<p class="mt-1 text-sm text-gray-500">{description}</p>
		</div>
	</div>
	<div class="min-w-0"><slot /></div>
</div>
