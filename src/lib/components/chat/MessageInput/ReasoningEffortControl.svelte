<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { fly } from 'svelte/transition';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import type { ReasoningLevel, ReasoningProfile } from '$lib/apis';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ClockRotateRight from '$lib/components/icons/ClockRotateRight.svelte';
	import QuestionMarkCircle from '$lib/components/icons/QuestionMarkCircle.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import { mobile } from '$lib/stores';
	import {
		DEFAULT_REASONING_LEVEL,
		getReasoningLabel,
		getReasoningLevelIndex,
		REASONING_LEVELS
	} from '$lib/utils/reasoning';

	const i18n: Writable<i18nType> = getContext('i18n');
	const MAX_INDEX = REASONING_LEVELS.length - 1;
	const PIXEL_COLUMNS = 30;
	const PIXEL_COUNT = PIXEL_COLUMNS * 4;

	const palettes = {
		gpt: {
			accent: ['#858985', '#858985', '#858985', '#7188a7', '#1266dc'],
			lightInk: ['#60645f', '#60645f', '#60645f', '#58708e', '#0955bc'],
			darkInk: ['#c2c5c1', '#c2c5c1', '#c2c5c1', '#a9bbd3', '#8dbaff'],
			lightSoft: ['#efefed', '#efefed', '#efefed', '#edf1f6', '#e7f0ff'],
			darkSoft: ['#2d2f2d', '#2d2f2d', '#2d2f2d', '#29313b', '#1d3152']
		},
		claude: {
			accent: ['#858985', '#858985', '#858985', '#8c7fa1', '#8546d5'],
			lightInk: ['#60645f', '#60645f', '#60645f', '#716482', '#7030bd'],
			darkInk: ['#c2c5c1', '#c2c5c1', '#c2c5c1', '#c8b9da', '#d1afff'],
			lightSoft: ['#efefed', '#efefed', '#efefed', '#f1edf4', '#f3eaff'],
			darkSoft: ['#2d2f2d', '#2d2f2d', '#2d2f2d', '#342e3a', '#41275a']
		}
	};

	export let profile: ReasoningProfile;
	export let level: ReasoningLevel = DEFAULT_REASONING_LEVEL;

	let show = false;
	let sliderElement: HTMLDivElement;
	let dragging = false;
	let dragRatio = getReasoningLevelIndex(level) / MAX_INDEX;
	let visualRatio = dragRatio;
	let labelDirection = 1;

	$: selectedIndex = getReasoningLevelIndex(level);
	$: label = getReasoningLabel(profile, level);
	$: palette = palettes[profile];
	$: accent = palette.accent[selectedIndex];
	$: accentInk = palette.lightInk[selectedIndex];
	$: accentInkDark = palette.darkInk[selectedIndex];
	$: accentSoft = palette.lightSoft[selectedIndex];
	$: accentSoftDark = palette.darkSoft[selectedIndex];
	$: if (!dragging) {
		visualRatio = selectedIndex / MAX_INDEX;
		dragRatio = visualRatio;
	}

	const setLevelIndex = (nextIndex: number) => {
		const boundedIndex = Math.max(0, Math.min(MAX_INDEX, nextIndex));
		if (boundedIndex !== selectedIndex) {
			labelDirection = boundedIndex > selectedIndex ? 1 : -1;
			level = REASONING_LEVELS[boundedIndex];
		}
	};

	const ratioFromPointer = (event: PointerEvent) => {
		const bounds = sliderElement.getBoundingClientRect();
		const edgePadding = 12;
		return Math.min(
			1,
			Math.max(0, (event.clientX - bounds.left - edgePadding) / (bounds.width - edgePadding * 2))
		);
	};

	const updateDrag = (event: PointerEvent) => {
		dragRatio = ratioFromPointer(event);
		visualRatio = dragRatio;
		setLevelIndex(Math.round(dragRatio * MAX_INDEX));
	};

	const startDrag = (event: PointerEvent) => {
		dragging = true;
		sliderElement.setPointerCapture(event.pointerId);
		updateDrag(event);
	};

	const finishDrag = (event: PointerEvent) => {
		if (!dragging) return;
		updateDrag(event);
		dragging = false;
		if (sliderElement.hasPointerCapture(event.pointerId)) {
			sliderElement.releasePointerCapture(event.pointerId);
		}
		visualRatio = selectedIndex / MAX_INDEX;
		dragRatio = visualRatio;
	};

	const handleKeydown = (event: KeyboardEvent) => {
		let nextIndex = selectedIndex;
		if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') nextIndex -= 1;
		else if (event.key === 'ArrowRight' || event.key === 'ArrowUp') nextIndex += 1;
		else if (event.key === 'Home') nextIndex = 0;
		else if (event.key === 'End') nextIndex = MAX_INDEX;
		else return;

		event.preventDefault();
		setLevelIndex(nextIndex);
	};

	const handleOpenChange = async (state: boolean) => {
		show = state;
		if (state) {
			await tick();
			sliderElement?.focus({ preventScroll: true });
		}
	};
</script>

<span
	class="reasoning-control"
	style:--reasoning-accent={accent}
	style:--reasoning-ink={accentInk}
	style:--reasoning-ink-dark={accentInkDark}
	style:--reasoning-soft={accentSoft}
	style:--reasoning-soft-dark={accentSoftDark}
>
	<Dropdown
		bind:show
		side="top"
		align="start"
		sideOffset={8}
		contentClass="reasoning-effort-popover"
		onOpenChange={handleOpenChange}
	>
		<button
			type="button"
			class="reasoning-trigger"
			aria-label={`${$i18n.t('Reasoning Effort')}: ${label}`}
		>
			<Sparkles className="size-4 shrink-0" strokeWidth="1.75" />
			<span class="trigger-copy"
				><span class="trigger-prefix">{$i18n.t('Reason')}</span>
				<span aria-hidden="true">&middot;</span>
				{label}</span
			>
		</button>

		<section
			slot="content"
			class:max-mode={selectedIndex === MAX_INDEX}
			class="reasoning-panel"
			style:--reasoning-accent={accent}
			style:--reasoning-ink={accentInk}
			style:--reasoning-ink-dark={accentInkDark}
			style:--reasoning-soft={accentSoft}
			style:--reasoning-soft-dark={accentSoftDark}
			aria-label={$i18n.t('Reasoning Effort')}
		>
			<div class="panel-head">
				<div class="title-line">
					<span>{$i18n.t('Reasoning Effort')}</span>
					<span class="effort-window">
						{#key label}
							<strong
								in:fly={{ y: labelDirection > 0 ? 18 : -18, duration: 180 }}
								out:fly={{ y: labelDirection > 0 ? -18 : 18, duration: 180 }}>{label}</strong
							>
						{/key}
					</span>
				</div>

				<div class="head-actions">
					<Tooltip
						content={$i18n.t('Higher reasoning effort may use more time and tokens.')}
						placement="top"
					>
						<button type="button" class="icon-action" aria-label={$i18n.t('Reasoning Effort')}>
							<QuestionMarkCircle className="size-3.5" />
						</button>
					</Tooltip>
					<Tooltip content={$i18n.t('Reset to default')} placement="top">
						<button
							type="button"
							class="icon-action"
							aria-label={$i18n.t('Reset to default')}
							on:click={() => setLevelIndex(getReasoningLevelIndex(DEFAULT_REASONING_LEVEL))}
						>
							<ClockRotateRight className="size-3.5" />
						</button>
					</Tooltip>
				</div>
			</div>

			<div class="spectrum-labels" aria-hidden="true">
				<span>{$i18n.t('Faster')}</span>
				<span>{$i18n.t('Smarter')}</span>
			</div>

			<div class="slider-wrap">
				<div
					bind:this={sliderElement}
					class:dragging
					class="snap-slider"
					role="slider"
					tabindex="0"
					aria-label={$i18n.t('Reasoning Effort')}
					aria-valuemin="0"
					aria-valuemax={MAX_INDEX}
					aria-valuenow={selectedIndex}
					aria-valuetext={label}
					on:pointerdown={startDrag}
					on:pointermove={(event) => dragging && updateDrag(event)}
					on:pointerup={finishDrag}
					on:pointercancel={finishDrag}
					on:keydown={handleKeydown}
				>
					<div class="slider-rail">
						<div class="pixel-track" aria-hidden="true">
							{#each Array(PIXEL_COUNT) as _, index}
								{@const column = index % PIXEL_COLUMNS}
								{@const activeColumns = Math.max(1, Math.round(visualRatio * PIXEL_COLUMNS))}
								<span
									class:active={column < activeColumns}
									class="pixel-cell"
									style={`--cell-opacity: ${0.34 + (column / (PIXEL_COLUMNS - 1)) * 0.58}; --cell-delay: ${-(PIXEL_COLUMNS - 1 - column) * 18}ms`}
								></span>
							{/each}
						</div>

						<div class="energy-trail" aria-hidden="true">
							{#each Array(14) as _, index}
								<span
									class="trail-particle"
									style={`--particle-top: ${3 + ((index * 11) % 29)}px; --particle-width: ${6 + (index % 5) * 4}px; --particle-height: ${index % 3 === 0 ? 2 : 1}px; --particle-duration: ${560 + (index % 6) * 82}ms; --particle-delay: ${-index * 79}ms; --particle-travel: ${108 + (index % 7) * 28}px`}
								></span>
							{/each}
						</div>
					</div>

					<div class="slot-markers" aria-hidden="true">
						{#each REASONING_LEVELS as _, index}
							<span class:active={index === selectedIndex} class="slot-marker"></span>
						{/each}
					</div>

					<span class="snap-handle" style:left={`${visualRatio * 100}%`} aria-hidden="true"></span>
				</div>
			</div>
		</section>
	</Dropdown>
</span>

{#if show && $mobile}
	<button
		type="button"
		class="mobile-scrim"
		aria-label={$i18n.t('Close')}
		on:click={() => (show = false)}
	></button>
{/if}

<style>
	.reasoning-trigger {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		height: 30px;
		max-width: 168px;
		padding: 0 9px;
		border: 1px solid color-mix(in srgb, var(--reasoning-accent) 28%, transparent);
		border-radius: 999px;
		background: var(--reasoning-soft);
		color: var(--reasoning-ink);
		font-size: 12px;
		font-weight: 650;
		transition:
			border-color 160ms ease,
			background-color 160ms ease;
	}

	:global(.dark) .reasoning-trigger {
		background: var(--reasoning-soft-dark);
		color: var(--reasoning-ink-dark);
	}

	.reasoning-trigger:hover {
		border-color: color-mix(in srgb, var(--reasoning-accent) 52%, transparent);
		background: color-mix(in srgb, var(--reasoning-soft) 76%, white);
	}

	:global(.dark) .reasoning-trigger:hover {
		background: color-mix(in srgb, var(--reasoning-soft-dark) 82%, #202220);
	}

	.trigger-copy {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	:global(.reasoning-effort-popover) {
		width: min(344px, calc(100vw - 40px));
		overflow: visible !important;
	}

	.reasoning-panel {
		width: 100%;
		padding: 14px;
		border: 1px solid color-mix(in srgb, var(--reasoning-accent) 28%, #dedfd9);
		border-radius: 8px;
		background: white;
		box-shadow:
			0 18px 48px rgba(26, 30, 27, 0.14),
			0 3px 12px rgba(26, 30, 27, 0.08);
		color: #171817;
	}

	:global(.dark) .reasoning-panel {
		border-color: color-mix(in srgb, var(--reasoning-accent) 28%, #3c3f3b);
		background: #202220;
		box-shadow:
			0 22px 56px rgba(0, 0, 0, 0.44),
			0 3px 12px rgba(0, 0, 0, 0.28);
		color: #f5f5f1;
	}

	.panel-head,
	.title-line,
	.head-actions,
	.spectrum-labels {
		display: flex;
		align-items: center;
	}

	.panel-head {
		justify-content: space-between;
		gap: 8px;
	}

	.title-line {
		min-width: 0;
		gap: 5px;
		font-size: 13px;
		font-weight: 620;
	}

	.effort-window {
		position: relative;
		display: inline-flex;
		align-items: center;
		width: 76px;
		height: 18px;
		overflow: hidden;
		color: var(--reasoning-ink);
	}

	:global(.dark) .effort-window {
		color: var(--reasoning-ink-dark);
	}

	.effort-window strong {
		position: absolute;
		left: 0;
		white-space: nowrap;
	}

	.head-actions {
		gap: 1px;
	}

	.icon-action {
		display: grid;
		place-items: center;
		width: 23px;
		height: 23px;
		padding: 0;
		border: 0;
		border-radius: 50%;
		background: transparent;
		color: #72746f;
	}

	.icon-action:hover {
		background: #f1f1ee;
		color: #171817;
	}

	:global(.dark) .icon-action:hover {
		background: #292b29;
		color: #f5f5f1;
	}

	.spectrum-labels {
		justify-content: space-between;
		margin-top: 15px;
		color: #72746f;
		font-size: 12px;
		font-weight: 620;
	}

	.slider-wrap {
		position: relative;
		height: 46px;
		margin-top: 4px;
	}

	.snap-slider {
		position: absolute;
		inset: 0;
		border-radius: 8px;
		outline: none;
		touch-action: none;
		user-select: none;
	}

	.snap-slider:focus-visible {
		box-shadow: 0 0 0 3px var(--reasoning-soft);
	}

	.slider-rail {
		position: absolute;
		inset: 4px 8px 8px;
		overflow: hidden;
		border: 1px solid #e9eae5;
		border-radius: 8px;
		background: #f1f1ee;
	}

	:global(.dark) .slider-rail {
		border-color: #30332f;
		background: #292b29;
	}

	.pixel-track {
		position: absolute;
		inset: 4px;
		display: grid;
		grid-template-columns: repeat(30, minmax(0, 1fr));
		grid-template-rows: repeat(4, minmax(0, 1fr));
		gap: 1.5px;
		overflow: hidden;
		pointer-events: none;
	}

	.pixel-cell {
		min-width: 0;
		min-height: 0;
		border-radius: 1px;
		background: #dedfd9;
		opacity: 0.42;
		transition:
			background-color 160ms ease,
			opacity 160ms ease;
	}

	:global(.dark) .pixel-cell {
		background: #3c3f3b;
	}

	.pixel-cell.active {
		background: var(--reasoning-accent);
		opacity: var(--cell-opacity, 0.74);
	}

	.slot-markers {
		position: absolute;
		z-index: 2;
		left: 17px;
		right: 17px;
		bottom: 0;
		display: flex;
		justify-content: space-between;
		pointer-events: none;
	}

	.slot-marker {
		width: 3px;
		height: 3px;
		border-radius: 50%;
		background: #dedfd9;
		transition:
			background-color 160ms ease,
			transform 160ms ease;
	}

	.slot-marker.active {
		background: var(--reasoning-accent);
		transform: scale(1.45);
	}

	.snap-handle {
		position: absolute;
		z-index: 5;
		top: 2px;
		width: 21px;
		height: 36px;
		border: 2px solid var(--reasoning-accent);
		border-radius: 8px;
		background: white;
		box-shadow: 0 3px 10px rgba(20, 22, 20, 0.22);
		transform: translateX(-50%);
		transition:
			left 300ms cubic-bezier(0.2, 0.86, 0.28, 1.08),
			transform 160ms ease,
			border-color 160ms ease,
			box-shadow 160ms ease;
	}

	:global(.dark) .snap-handle {
		background: #202220;
	}

	.snap-slider.dragging .snap-handle {
		transform: translateX(-50%) scale(1.08);
		transition: transform 120ms ease;
	}

	.snap-handle::after {
		position: absolute;
		top: 7px;
		bottom: 7px;
		left: 50%;
		width: 2px;
		border-radius: 2px;
		background: color-mix(in srgb, var(--reasoning-accent) 72%, white);
		content: '';
		transform: translateX(-50%);
	}

	.energy-trail {
		position: absolute;
		z-index: 4;
		inset: 0;
		display: none;
		overflow: hidden;
		border-radius: inherit;
		pointer-events: none;
	}

	.energy-trail::before {
		position: absolute;
		top: 3px;
		right: -22%;
		bottom: 3px;
		width: 28%;
		border-radius: 8px;
		background: linear-gradient(
			90deg,
			transparent,
			color-mix(in srgb, var(--reasoning-accent) 14%, transparent) 32%,
			color-mix(in srgb, var(--reasoning-accent) 62%, transparent) 78%,
			color-mix(in srgb, var(--reasoning-accent) 12%, white)
		);
		content: '';
		opacity: 0;
		transform: skewX(-16deg);
	}

	.energy-trail::after {
		position: absolute;
		top: 50%;
		right: 5px;
		width: 8px;
		height: 25px;
		border: 1px solid color-mix(in srgb, var(--reasoning-accent) 76%, transparent);
		border-right: 0;
		border-radius: 8px 0 0 8px;
		content: '';
		opacity: 0;
		transform: translateY(-50%) scaleX(0.35);
		transform-origin: right center;
	}

	.trail-particle {
		position: absolute;
		left: calc(100% - 13px);
		top: var(--particle-top);
		width: var(--particle-width);
		height: var(--particle-height);
		border-radius: 2px;
		background: color-mix(in srgb, var(--reasoning-accent) 58%, white);
		box-shadow: 0 0 8px color-mix(in srgb, var(--reasoning-accent) 78%, transparent);
		opacity: 0;
	}

	.max-mode .energy-trail {
		display: block;
	}

	.max-mode .energy-trail::before {
		animation: energy-sweep 1.35s cubic-bezier(0.18, 0.72, 0.22, 1) infinite;
	}

	.max-mode .energy-trail::after {
		animation: energy-shock 1.35s ease-out infinite;
	}

	.max-mode .trail-particle {
		animation: trail-back var(--particle-duration) linear infinite;
		animation-delay: var(--particle-delay);
	}

	.max-mode .pixel-cell.active {
		animation: pixel-surge 1.15s ease-in-out infinite;
		animation-delay: var(--cell-delay, 0ms);
	}

	.max-mode .snap-handle {
		animation: handle-charge 1.35s ease-in-out infinite;
	}

	.max-mode .snap-handle::after {
		animation: handle-core 0.7s ease-in-out infinite alternate;
	}

	.mobile-scrim {
		position: fixed;
		z-index: 9998;
		inset: 0;
		border: 0;
		background: rgba(15, 17, 16, 0.34);
		backdrop-filter: blur(2px);
	}

	@keyframes pixel-surge {
		0%,
		100% {
			opacity: calc(var(--cell-opacity, 0.74) * 0.84);
			transform: scaleY(0.92);
		}
		42% {
			opacity: var(--cell-opacity, 0.74);
			transform: scaleY(1);
		}
	}

	@keyframes energy-sweep {
		0% {
			right: -22%;
			opacity: 0;
		}
		12% {
			opacity: 0.38;
		}
		72% {
			opacity: 0.18;
		}
		100% {
			right: 96%;
			opacity: 0;
		}
	}

	@keyframes energy-shock {
		0%,
		28% {
			opacity: 0;
			transform: translateY(-50%) scaleX(0.35);
		}
		38% {
			opacity: 0.46;
		}
		76%,
		100% {
			right: 24px;
			opacity: 0;
			transform: translateY(-50%) scaleX(1.65);
		}
	}

	@keyframes handle-charge {
		0%,
		100% {
			box-shadow:
				0 0 0 3px var(--reasoning-soft),
				0 0 10px color-mix(in srgb, var(--reasoning-accent) 38%, transparent),
				0 3px 10px rgba(20, 22, 20, 0.22);
		}
		50% {
			box-shadow:
				0 0 0 4px color-mix(in srgb, var(--reasoning-accent) 12%, transparent),
				0 0 18px color-mix(in srgb, var(--reasoning-accent) 58%, transparent),
				0 3px 12px rgba(20, 22, 20, 0.28);
		}
	}

	@keyframes handle-core {
		from {
			opacity: 0.58;
			box-shadow: 0 0 3px color-mix(in srgb, var(--reasoning-accent) 48%, transparent);
		}
		to {
			opacity: 1;
			box-shadow: 0 0 9px color-mix(in srgb, var(--reasoning-accent) 88%, transparent);
		}
	}

	@keyframes trail-back {
		0% {
			opacity: 0;
			transform: translateX(0) scaleX(0.22);
		}
		10% {
			opacity: 1;
		}
		64% {
			opacity: 0.62;
		}
		100% {
			opacity: 0;
			transform: translateX(calc(var(--particle-travel) * -1)) scaleX(1.7);
		}
	}

	@media (max-width: 760px) {
		:global(.reasoning-effort-popover) {
			top: auto !important;
			right: 14px !important;
			bottom: 14px !important;
			left: 14px !important;
			width: auto;
		}
	}

	@media (max-width: 480px) {
		.trigger-prefix {
			display: none;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.reasoning-panel *,
		.reasoning-panel *::before,
		.reasoning-panel *::after {
			animation-duration: 0.01ms !important;
			animation-iteration-count: 1 !important;
			transition-duration: 0.01ms !important;
		}
	}
</style>
