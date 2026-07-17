<script lang="ts">
	import { onDestroy } from 'svelte';
	import type { Chart as ChartInstance } from 'chart.js';

	export let history: Array<{ date: string; count: number }> = [];

	let chartCanvas: HTMLCanvasElement;
	let chartInstance: ChartInstance | null = null;
	let Chart: typeof import('chart.js/auto').default | null = null;

	const draw = async () => {
		if (!chartCanvas || !history.length) return;
		if (!Chart) Chart = (await import('chart.js/auto')).default;
		chartInstance?.destroy();
		chartInstance = new Chart(chartCanvas, {
			type: 'line',
			data: {
				labels: history.map((item) =>
					new Date(`${item.date}T00:00:00Z`).toLocaleDateString(undefined, {
						month: 'short',
						day: 'numeric'
					})
				),
				datasets: [
					{
						label: '调用量',
						data: history.map((item) => item.count),
						borderColor: '#16a34a',
						backgroundColor: 'rgba(22, 163, 74, 0.08)',
						borderWidth: 2,
						pointRadius: 0,
						pointHoverRadius: 3,
						fill: true,
						tension: 0.35
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				interaction: { intersect: false, mode: 'index' },
				scales: {
					x: { grid: { display: false }, ticks: { maxTicksLimit: 6, color: '#6b7280' } },
					y: {
						beginAtZero: true,
						ticks: { precision: 0, color: '#6b7280' },
						grid: { color: 'rgba(107,114,128,0.12)' }
					}
				},
				animation: { duration: 250 }
			}
		});
	};

	$: if (chartCanvas && history) draw();

	onDestroy(() => chartInstance?.destroy());
</script>

{#if history.length && history.some((item) => item.count > 0)}
	<div class="h-52 w-full"><canvas bind:this={chartCanvas}></canvas></div>
{:else}
	<div class="flex h-52 items-center justify-center text-sm text-gray-500">近期暂无调用记录</div>
{/if}
