<script lang="ts">
	import { onDestroy } from 'svelte';
	import Image from '$lib/components/common/Image.svelte';
	import { resolveFileContentUrl } from '$lib/utils/fileUrls';

	type MediaFile = {
		type?: string;
		content_type?: string;
		url?: string;
		id?: string;
		name?: string;
	};

	type MediaGeneration = {
		tool_call_id: string;
		media_type?: 'image' | 'video';
		operation?: 'generate' | 'edit';
		phase?: 'start' | 'success' | 'failure';
		files?: MediaFile[];
	};

	type WriterState = {
		index: number;
		cursor: number;
		phase: 'typing' | 'holding' | 'deleting';
		phrases: string[];
	};

	export let generations: MediaGeneration[] = [];
	export let alt = '';

	const captionSets: Record<string, string[]> = {
		image: ['正在理解需求...', '准备草图...', '正在发送请求...', '正在生成图片...'],
		edit: ['正在理解图片...', '准备修改...', '正在发送请求...', '正在编辑图片...'],
		video: ['正在理解需求...', '准备草图...', '正在发送请求...', '正在生成视频...']
	};

	let captionByKey: Record<string, string> = {};
	const writers: Record<string, WriterState> = {};
	const writerTimers: Record<string, ReturnType<typeof setTimeout> | null> = {};

	const visibleFiles = (generation: MediaGeneration): MediaFile[] =>
		(generation.files ?? []).filter((file) => file?.url || file?.id);
	const keyOf = (generation: MediaGeneration) => generation.tool_call_id;
	const phrasesOf = (generation: MediaGeneration) =>
		generation.media_type === 'video'
			? captionSets.video
			: generation.operation === 'edit'
				? captionSets.edit
				: captionSets.image;

	function setCaption(key: string, value: string) {
		captionByKey = { ...captionByKey, [key]: value };
	}

	function clearWriterTimer(key: string) {
		if (writerTimers[key]) clearTimeout(writerTimers[key]);
		writerTimers[key] = null;
	}

	function stopWriter(key: string, clearCaption = true) {
		clearWriterTimer(key);
		delete writers[key];
		if (clearCaption) {
			const next = { ...captionByKey };
			delete next[key];
			captionByKey = next;
		}
	}

	function scheduleWriter(key: string, delay: number) {
		clearWriterTimer(key);
		writerTimers[key] = setTimeout(() => typeCaption(key), delay);
	}

	function typeCaption(key: string) {
		const writer = writers[key];
		if (!writer) return;
		const phrase = writer.phrases[writer.index];
		if (!phrase) {
			stopWriter(key, false);
			return;
		}

		if (writer.phase === 'typing') {
			writer.cursor += 1;
			setCaption(key, phrase.slice(0, writer.cursor));
			if (writer.cursor >= phrase.length) {
				writer.phase = 'holding';
				if (writer.index === writer.phrases.length - 1) {
					writerTimers[key] = null;
				} else {
					scheduleWriter(key, 1500);
				}
			} else {
				scheduleWriter(key, 112);
			}
			return;
		}

		if (writer.phase === 'holding') {
			if (writer.index === writer.phrases.length - 1) {
				writerTimers[key] = null;
				return;
			}
			writer.phase = 'deleting';
			scheduleWriter(key, 92);
			return;
		}

		writer.cursor = Math.max(0, writer.cursor - 1);
		setCaption(key, phrase.slice(0, writer.cursor));
		if (writer.cursor === 0) {
			writer.index += 1;
			writer.phase = 'typing';
			scheduleWriter(key, 360);
		} else {
			scheduleWriter(key, 92);
		}
	}

	function startWriter(generation: MediaGeneration) {
		const key = keyOf(generation);
		if (!key || writers[key]) return;
		writers[key] = { index: 0, cursor: 0, phase: 'typing', phrases: phrasesOf(generation) };
		setCaption(key, '');
		typeCaption(key);
	}

	function cleanupKey(key: string) {
		stopWriter(key);
	}

	function syncGenerations(items: MediaGeneration[]) {
		const activeKeys = new Set((items ?? []).filter((item) => item.phase !== 'failure').map(keyOf));
		for (const key of Object.keys(writers)) {
			if (!activeKeys.has(key)) cleanupKey(key);
		}
		for (const generation of items ?? []) {
			const key = keyOf(generation);
			if (!key || generation.phase === 'failure') continue;
			if (visibleFiles(generation).length > 0) {
				stopWriter(key, false);
			} else {
				startWriter(generation);
			}
		}
	}

	function dotMatrix(node: HTMLCanvasElement) {
		const stage = node.parentElement;
		if (!stage) return { destroy: () => undefined };

		let frame: number | null = null;
		const startedAt = performance.now();
		const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

		const draw = (now: number) => {
			frame = null;
			if (!node.isConnected) {
				return;
			}

			const width = Math.max(1, Math.floor(stage.clientWidth));
			const height = Math.max(1, Math.floor(stage.clientHeight));
			const dpr = Math.min(window.devicePixelRatio || 1, 2);
			if (node.width !== width * dpr || node.height !== height * dpr) {
				node.width = width * dpr;
				node.height = height * dpr;
				node.style.width = `${width}px`;
				node.style.height = `${height}px`;
			}

			const context = node.getContext('2d');
			if (!context) return;
			context.setTransform(dpr, 0, 0, dpr, 0, 0);
			context.clearRect(0, 0, width, height);

			const darkTheme = document.documentElement.classList.contains('dark');
			const dotColor = darkTheme ? [87, 145, 255] : [48, 106, 214];
			context.fillStyle = darkTheme ? '#15191f' : '#f7f9fc';
			context.fillRect(0, 0, width, height);
			const centerX = width * 0.5;
			const centerY = height * 0.54;
			const spacing = Math.max(12, Math.min(18, width / 31));
			const columns = Math.max(25, Math.ceil(width / spacing) + 2);
			const rows = Math.max(22, Math.ceil(height / spacing) + 2);
			const rotation = reduceMotion ? 0 : (now - startedAt) * 0.000085;
			const pulse = reduceMotion ? 0.66 : (Math.sin((now - startedAt) * 0.00135) + 1) * 0.5;
			const maxDistance = Math.hypot(columns * spacing * 0.5, rows * spacing * 0.5);

			for (let row = 0; row < rows; row += 1) {
				for (let column = 0; column < columns; column += 1) {
					const sourceX = (column - (columns - 1) / 2) * spacing;
					const sourceY = (row - (rows - 1) / 2) * spacing;
					const distance = Math.hypot(sourceX, sourceY);
					const falloff = Math.max(0, 1 - distance / maxDistance);
					const localPulse = (Math.sin((now - startedAt) * 0.0011 + distance * 0.022) + 1) * 0.5;
					const x = centerX + sourceX * Math.cos(rotation) - sourceY * Math.sin(rotation);
					const y = centerY + sourceX * Math.sin(rotation) + sourceY * Math.cos(rotation);
					const radius = 0.8 + falloff * (1.35 + localPulse * 0.9) + pulse * falloff * 0.45;
					const alpha = 0.08 + falloff * (0.28 + localPulse * 0.28) + pulse * falloff * 0.12;

					context.beginPath();
					context.fillStyle = `rgba(${dotColor[0]}, ${dotColor[1]}, ${dotColor[2]}, ${Math.min(0.94, alpha)})`;
					context.arc(x, y, radius, 0, Math.PI * 2);
					context.fill();
				}
			}

			frame = requestAnimationFrame(draw);
		};

		const scheduleDraw = () => {
			if (frame === null) frame = requestAnimationFrame(draw);
		};
		const handlePageVisible = () => {
			if (document.visibilityState !== 'visible') return;
			if (frame !== null) cancelAnimationFrame(frame);
			frame = null;
			scheduleDraw();
		};
		const resizeObserver =
			typeof ResizeObserver !== 'undefined' ? new ResizeObserver(scheduleDraw) : null;
		resizeObserver?.observe(stage);
		document.addEventListener('visibilitychange', handlePageVisible);
		window.addEventListener('pageshow', handlePageVisible);
		scheduleDraw();

		return {
			destroy() {
				if (frame !== null) cancelAnimationFrame(frame);
				resizeObserver?.disconnect();
				document.removeEventListener('visibilitychange', handlePageVisible);
				window.removeEventListener('pageshow', handlePageVisible);
			}
		};
	}

	$: syncGenerations(generations);

	onDestroy(() => {
		for (const key of Object.keys(writers)) cleanupKey(key);
	});
</script>

{#each generations.filter((item) => item.phase !== 'failure') as generation (generation.tool_call_id)}
	{@const key = generation.tool_call_id}
	{@const files = visibleFiles(generation)}
	<div class="media-generation-card" data-media-call-id={key}>
		{#if files.length === 0}
			<div class="media-generation-placeholder" aria-busy="true" aria-label="正在生成">
				<div class="media-generation-caption" aria-live="polite">
					{captionByKey[key] || '正在理解需求...'}
				</div>
				<canvas class="media-generation-grid" use:dotMatrix aria-hidden="true"></canvas>
			</div>
		{:else}
			<div class="media-generation-result">
				{#each files as file}
					{#if file.type === 'video' || (file.content_type ?? '').startsWith('video/')}
						<!-- svelte-ignore a11y-media-has-caption -->
						<video
							controls
							preload="metadata"
							src={resolveFileContentUrl(file.id || file.url || '')}
							class="max-h-96 max-w-full rounded-xl bg-black"
						></video>
					{:else}
						<Image src={resolveFileContentUrl(file.id || file.url || '')} {alt} />
					{/if}
				{/each}
			</div>
		{/if}
	</div>
{/each}

<style>
	.media-generation-card {
		width: 100%;
		margin: 0.35rem 0;
	}
	.media-generation-placeholder {
		position: relative;
		width: min(100%, 42rem);
		aspect-ratio: 1.45;
		min-height: 15rem;
		overflow: hidden;
		border: 1px solid rgb(148 163 184 / 0.24);
		border-radius: 1rem;
		background: #f7f9fc;
		color: #1e293b;
	}
	:global(.dark) .media-generation-placeholder {
		border-color: rgb(148 163 184 / 0.2);
		background: #15191f;
		color: #e5e7eb;
	}
	.media-generation-caption {
		position: absolute;
		z-index: 2;
		top: 5.5%;
		left: 3.5%;
		min-height: 1.4rem;
		font-size: 0.95rem;
		font-weight: 500;
		letter-spacing: 0;
		text-shadow: 0 1px 8px rgb(255 255 255 / 0.35);
	}
	:global(.dark) .media-generation-caption {
		text-shadow: 0 1px 8px rgb(0 0 0 / 0.42);
	}
	.media-generation-grid {
		position: absolute;
		inset: 0;
		display: block;
		width: 100%;
		height: 100%;
	}
	.media-generation-result {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		width: 100%;
	}
	@media (prefers-reduced-motion: reduce) {
		.media-generation-grid {
			opacity: 0.8;
		}
	}
</style>
