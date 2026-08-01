<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	const sections = [
		{ href: '/admin/email/settings', label: '邮箱设置' },
		{ href: '/admin/email/templates', label: '邮件模板' },
		{ href: '/admin/email/deliveries', label: '发送记录' }
	];

	$: activeRoute =
		sections.find((section) => $page.url.pathname.startsWith(section.href))?.href ??
		sections[0].href;
</script>

<div class="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-4 sm:px-6">
	<div class="flex flex-col gap-3 border-b border-gray-100 pb-3 dark:border-gray-850">
		<h1 class="text-xl font-medium">邮箱</h1>
		<select
			class="w-full rounded-lg border border-gray-100 bg-transparent px-3 py-2 text-sm dark:border-gray-850 sm:hidden"
			value={activeRoute}
			on:change={(event) => goto(event.currentTarget.value)}
			aria-label="邮箱管理页面"
		>
			{#each sections as section}
				<option value={section.href}>{section.label}</option>
			{/each}
		</select>
		<nav class="hidden gap-5 text-sm sm:flex" aria-label="邮箱管理">
			{#each sections as section}
				<a
					href={section.href}
					class={$page.url.pathname.startsWith(section.href)
						? 'font-medium text-black dark:text-white'
						: 'text-gray-500 hover:text-black dark:hover:text-white'}
				>
					{section.label}
				</a>
			{/each}
		</nav>
	</div>
	<div class="min-w-0"><slot /></div>
</div>
