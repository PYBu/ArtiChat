<script lang="ts">
	import { decode } from 'html-entities';
	import { v4 as uuidv4 } from 'uuid';

	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import dayjs from '$lib/dayjs';
	import duration from 'dayjs/plugin/duration';
	import relativeTime from 'dayjs/plugin/relativeTime';

	dayjs.extend(duration);
	dayjs.extend(relativeTime);

	async function loadLocale(locales) {
		if (!locales || !Array.isArray(locales)) {
			return;
		}
		for (const locale of locales) {
			try {
				dayjs.locale(locale);
				break; // Stop after successfully loading the first available locale
			} catch (error) {
				console.error(`Could not load locale '${locale}':`, error);
			}
		}
	}

	// Assuming $i18n.languages is an array of language codes
	$: loadLocale($i18n.languages);

	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	import ChevronUp from '../icons/ChevronUp.svelte';
	import ChevronDown from '../icons/ChevronDown.svelte';
	import Spinner from './Spinner.svelte';
	import { config } from '$lib/stores';
	import { resolveOperationStatus } from '$lib/utils/operationStatus';

	export let open = false;

	export let className = '';
	export let buttonClassName =
		'w-fit py-1 text-[0.9375rem] text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition';

	export let id = '';
	export let title = null;
	export let attributes = null;
	export let chevronClassName = 'size-3';
	export let chevronStrokeWidth = '2.75';

	export let chevron = false;
	export let grow = false;

	export let disabled = false;
	export let messageDone = false;
	export let hide = false;

	export let onChange: Function = () => {};

	const toggleOpen = () => {
		if (disabled) {
			return;
		}

		open = !open;
		onChange(open);
	};

	const collapsibleId = uuidv4();

	$: isDetailPending = attributes?.done !== 'true' && !messageDone;
	$: reasoningDuration = Number(attributes?.duration ?? 0);
	$: detailStatusId =
		attributes?.type === 'reasoning'
			? isDetailPending
				? 'reasoning.thinking'
				: attributes?.duration
					? reasoningDuration < 1
						? 'reasoning.thought_short'
						: reasoningDuration < 60
							? 'reasoning.thought_seconds'
							: 'reasoning.thought_human'
					: 'reasoning.thought'
			: attributes?.type === 'code_interpreter'
				? isDetailPending
					? 'code.analyzing'
					: 'code.analyzed'
				: null;
	$: detailStatus = detailStatusId
		? resolveOperationStatus(
				{
					status_id: detailStatusId,
					duration: attributes?.duration
				},
				$config?.ui?.operation_status
			)
		: null;
	$: detailStatusVisible = !detailStatus?.hidden;
	$: detailStatusText = detailStatusVisible ? detailStatus?.display_description : null;
</script>

<div {id} class={className}>
	{#if title !== null}
		<button
			type="button"
			class="{buttonClassName} block text-start disabled:cursor-default"
			aria-expanded={open}
			{disabled}
			on:click={toggleOpen}
		>
			<div
				class=" w-full flex items-center justify-between gap-2 {attributes?.done &&
				attributes?.done !== 'true' &&
				!messageDone
					? 'shimmer'
					: ''}
			"
			>
				{#if attributes?.done && attributes?.done !== 'true' && !messageDone}
					<div>
						<Spinner className="size-4" />
					</div>
				{/if}

				<div class="">
					{#if attributes?.type === 'reasoning'}
						{#if !detailStatusVisible}
							<span class="sr-only">{$i18n.t('Reasoning')}</span>
						{:else if detailStatusText}
							{detailStatusText}
						{:else if (attributes?.done === 'true' || messageDone) && attributes?.duration}
							{#if attributes.duration < 1}
								{$i18n.t('Thought for less than a second')}
							{:else if attributes.duration < 60}
								{$i18n.t('Thought for {{DURATION}} seconds', {
									DURATION: attributes.duration
								})}
							{:else}
								{$i18n.t('Thought for {{DURATION}}', {
									DURATION: dayjs.duration(attributes.duration, 'seconds').humanize()
								})}
							{/if}
						{:else if attributes?.done === 'true' || messageDone}
							{$i18n.t('Thought')}
						{:else}
							{$i18n.t('Thinking...')}
						{/if}
					{:else if attributes?.type === 'code_interpreter'}
						{#if !detailStatusVisible}
							<span class="sr-only">{$i18n.t('Code interpreter')}</span>
						{:else if detailStatusText}
							{detailStatusText}
						{:else if attributes?.done === 'true' || messageDone}
							{$i18n.t('Analyzed')}
						{:else}
							{$i18n.t('Analyzing...')}
						{/if}
					{:else}
						{title}
					{/if}
				</div>

				{#if !disabled}
					<div class="flex self-center translate-y-[1px]">
						{#if open}
							<ChevronUp strokeWidth={chevronStrokeWidth} className={chevronClassName} />
						{:else}
							<ChevronDown strokeWidth={chevronStrokeWidth} className={chevronClassName} />
						{/if}
					</div>
				{/if}
			</div>
		</button>
	{:else}
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<div
			class="{buttonClassName} cursor-pointer"
			on:click={(e) => {
				e.stopPropagation();
			}}
			on:pointerup={toggleOpen}
		>
			<div>
				<div class="flex items-start justify-between">
					<slot />

					{#if chevron}
						<div class="flex self-start translate-y-1">
							{#if open}
								<ChevronUp strokeWidth={chevronStrokeWidth} className={chevronClassName} />
							{:else}
								<ChevronDown strokeWidth={chevronStrokeWidth} className={chevronClassName} />
							{/if}
						</div>
					{/if}
				</div>

				{#if grow}
					{#if open && !hide}
						<div
							transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}
							on:pointerup={(e) => {
								e.stopPropagation();
							}}
						>
							<slot name="content" />
						</div>
					{/if}
				{/if}
			</div>
		</div>
	{/if}

	{#if !grow}
		{#if open && !hide}
			<div transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
				<slot name="content" />
			</div>
		{/if}
	{/if}
</div>
