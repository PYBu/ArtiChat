<script lang="ts">
	import { decode } from 'html-entities';
	import { getContext } from 'svelte';
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import WrenchSolid from '$lib/components/icons/WrenchSolid.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import CheckCircle from '$lib/components/icons/CheckCircle.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import FullHeightIframe from '$lib/components/common/FullHeightIframe.svelte';

	import { config, settings } from '$lib/stores';
	import { getToolCallFailureReason, resolveOperationStatus } from '$lib/utils/operationStatus';

	const i18n = getContext('i18n');

	export let id = '';
	export let tokens: Array<{
		summary?: string;
		attributes?: {
			type?: string;
			name?: string;
			done?: string;
			duration?: string;
			embeds?: string;
			arguments?: string;
			failed?: string;
		};
		text?: string;
	}> = [];

	export let messageDone = true;
	export let allowEmbeds = true;
	export let compactPreview = false;

	let open = $settings?.expandDetails ?? false;

	function parseJSONString(str: string) {
		try {
			return parseJSONString(JSON.parse(str));
		} catch (e) {
			return str;
		}
	}

	$: toolCallCount = tokens.filter((t) => t?.attributes?.type === 'tool_calls').length;
	$: reasoningCount = tokens.filter((t) => t?.attributes?.type === 'reasoning').length;
	$: hasPending =
		!messageDone &&
		tokens.some((t) => t?.attributes?.done !== undefined && t?.attributes?.done !== 'true');
	$: hasFailed = tokens.some((t) => {
		if (t?.attributes?.type !== 'tool_calls') return false;
		if (t.attributes?.failed === 'true') return true;
		const raw = decode(t.text ?? '');
		return Boolean(getToolCallFailureReason(undefined, raw));
	});

	$: codeInterpreterCount = tokens.filter((t) => t?.attributes?.type === 'code_interpreter').length;

	// Collect all embeds from tool_calls tokens
	$: allEmbeds = (() => {
		if (!allowEmbeds) return [];

		const result: Array<{ name: string; embed: string; args: string }> = [];
		for (const t of tokens) {
			if (t?.attributes?.type !== 'tool_calls') continue;
			const raw = decode(t.attributes?.embeds ?? '');
			try {
				const parsed = parseJSONString(raw);
				if (Array.isArray(parsed) && parsed.length > 0) {
					for (const embed of parsed) {
						result.push({
							name: t.attributes?.name ?? '',
							embed,
							args: decode(t.attributes?.arguments ?? '')
						});
					}
				}
			} catch {}
		}
		return result;
	})();

	$: summaryText = (() => {
		const parts = [];

		if (toolCallCount > 0) {
			// Group by tool name and show counts
			const nameCounts = {};
			tokens
				.filter((t) => t?.attributes?.type === 'tool_calls')
				.forEach((t) => {
					const name = t?.attributes?.name ?? 'tool';
					nameCounts[name] = (nameCounts[name] || 0) + 1;
				});

			const toolParts = Object.entries(nameCounts).map(([name, count]) =>
				count > 1 ? `${count} ${name}` : name
			);
			parts.push(...toolParts);
		}

		if (codeInterpreterCount > 0) {
			if (codeInterpreterCount === 1) {
				parts.push($i18n.t('Ran {{COUNT}} analysis', { COUNT: codeInterpreterCount }));
			} else {
				parts.push($i18n.t('Ran {{COUNT}} analyses', { COUNT: codeInterpreterCount }));
			}
		}

		const prefix = hasPending ? $i18n.t('Exploring') : $i18n.t('Explored');
		const detail = parts.join(', ');
		return detail;
	})();

	$: activityStatus = resolveOperationStatus(
		{ status_id: hasPending ? 'activity.exploring' : 'activity.explored' },
		$config?.ui?.operation_status
	);
	$: prefixText = activityStatus.hidden
		? ''
		: activityStatus.display_description ||
			(hasPending ? $i18n.t('Exploring') : $i18n.t('Explored'));
</script>

<div {id} class="w-full">
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<button
		class="w-fit py-0.5 text-left {compactPreview
			? 'text-xs'
			: 'text-[0.9375rem]'} text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition cursor-pointer"
		aria-label={$i18n.t('Toggle details')}
		aria-expanded={open}
		on:click={() => {
			open = !open;
		}}
	>
		<div class="flex items-center gap-1.5">
			<!-- Status icon -->
			{#if hasPending}
				<div>
					<Spinner className="size-4" />
				</div>
			{:else if hasFailed}
				<div class="text-red-500 dark:text-red-400">
					<XMark className="size-4" strokeWidth="2" />
				</div>
			{:else if toolCallCount > 0}
				<div class="text-emerald-500 dark:text-emerald-400">
					<CheckCircle className="size-4" strokeWidth="2" />
				</div>
			{:else}
				<div class="text-gray-400 dark:text-gray-500">
					<Sparkles className="size-3.5" />
				</div>
			{/if}

			<!-- Summary text -->
			<div class="flex-1 line-clamp-1">
				{#if prefixText}
					<span class="text-gray-600 dark:text-gray-300 {hasPending ? 'shimmer' : ''}"
						>{prefixText}</span
					>
				{/if}
				{#if summaryText}
					<span class="text-gray-400 dark:text-gray-500">{summaryText}</span>
				{/if}
			</div>

			<!-- Chevron -->
			<div class="flex shrink-0 self-center text-gray-400 dark:text-gray-500">
				{#if open}
					<ChevronUp strokeWidth="3.5" className="size-3" />
				{:else}
					<ChevronDown strokeWidth="3.5" className="size-3" />
				{/if}
			</div>
		</div>
	</button>

	{#if open}
		<div transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
			<div class="mb-1">
				<slot name="content" />
			</div>
		</div>
	{/if}

	{#if allEmbeds.length > 0}
		{#each allEmbeds as embedItem, idx}
			<div id={`${id}-embed-${idx}`}>
				<FullHeightIframe
					src={embedItem.embed}
					args={embedItem.args}
					allowScripts={true}
					allowForms={$settings?.iframeSandboxAllowForms ?? false}
					allowSameOrigin={$settings?.iframeSandboxAllowSameOrigin ?? false}
					allowPopups={true}
				/>
			</div>
		{/each}
	{/if}
</div>
