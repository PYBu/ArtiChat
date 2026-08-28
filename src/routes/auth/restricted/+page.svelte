<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	$: reason = $page.url.searchParams.get('reason');
	$: isRegion = reason === 'region';
	$: title = isRegion ? '我们无法为您所在的地区提供服务' : '您的连接请求被拒绝';
	$: description = isRegion
		? '当前服务暂不支持您所在的国家或地区。'
		: '当前网络地址不允许访问此服务。';
</script>

<svelte:head><title>{title}</title></svelte:head>

<div
	class="flex min-h-screen items-center justify-center bg-white px-6 text-center text-gray-900 dark:bg-black dark:text-gray-100"
>
	<div class="w-full max-w-md">
		<div
			class="mx-auto flex size-12 items-center justify-center rounded-full bg-gray-100 text-xl dark:bg-gray-900"
			aria-hidden="true"
		>
			!
		</div>
		<h1 class="mt-5 text-xl font-medium">{title}</h1>
		<p class="mt-2 text-sm text-gray-500">{description}</p>
		<button
			type="button"
			class="mt-6 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
			on:click={() => goto('/auth')}>返回登录</button
		>
	</div>
</div>
