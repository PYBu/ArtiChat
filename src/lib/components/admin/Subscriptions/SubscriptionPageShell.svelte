<script lang="ts">
	export let title: string;
	export let description: string;
</script>

<div class="operations-page mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6">
	<div class="flex items-start gap-3 border-b border-gray-100 pb-2.5 dark:border-gray-850">
		<a
			href="/admin/subscriptions"
			class="mt-0.5 inline-flex size-7 flex-none items-center justify-center rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850"
			aria-label="返回运营管理"
			title="返回运营管理"
		>
			<span aria-hidden="true">←</span>
		</a>
		<div class="min-w-0">
			<h1 class="text-[14px] font-medium">{title}</h1>
			<p class="mt-0.5 text-[11px] text-gray-500">{description}</p>
		</div>
	</div>
	<div class="min-w-0"><slot /></div>
</div>

<style>
	.operations-page :global(.text-2xl) {
		font-size: 1.25rem;
		line-height: 1.5rem;
	}

	.operations-page :global(.text-xl),
	.operations-page :global(.text-lg),
	.operations-page :global(.text-base) {
		font-size: 0.875rem;
		line-height: 1.25rem;
	}

	.operations-page :global(.text-sm) {
		font-size: 0.75rem;
		line-height: 1rem;
	}
</style>
