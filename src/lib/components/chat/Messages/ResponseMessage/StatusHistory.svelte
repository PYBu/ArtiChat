<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import StatusItem from './StatusHistory/StatusItem.svelte';
	import equal from 'fast-deep-equal';
	import {
		getVisibleOperationStatusHistory,
		type OperationStatus,
		type OperationStatusConfig
	} from '$lib/utils/operationStatus';
	export let statusHistory = [];
	export let operationStatus: OperationStatusConfig | null = null;
	export let expand = false;

	let showHistory = true;

	$: if (expand) {
		showHistory = true;
	} else {
		showHistory = false;
	}

	let history: OperationStatus[] = [];
	let visibleHistory: OperationStatus[] = [];
	let status = null;

	$: if (history && history.length > 0) {
		visibleHistory = getVisibleOperationStatusHistory(history, operationStatus);
		status = visibleHistory.at(-1);
	} else {
		visibleHistory = [];
		status = null;
	}

	$: if (!equal(statusHistory, history)) {
		history = statusHistory;
	}
</script>

{#if visibleHistory.length > 0}
	<div class="text-[0.9375rem] flex flex-col w-full">
		<button
			class="w-full"
			aria-label={$i18n.t('Toggle status history')}
			aria-expanded={showHistory}
			on:click={() => {
				showHistory = !showHistory;
			}}
		>
			<div class="flex items-start gap-2">
				<StatusItem {status} />
			</div>
		</button>

		{#if showHistory}
			<div class="flex flex-row">
				{#if visibleHistory.length > 1}
					<div class="w-full">
						{#each visibleHistory as status, idx}
							<div class="flex items-stretch gap-2 mb-1">
								<div class=" ">
									<div class="pt-3 px-1 mb-1.5">
										<span class="relative flex size-1.5 rounded-full justify-center items-center">
											<span
												class="relative inline-flex size-1.5 rounded-full bg-gray-500 dark:bg-gray-400"
											></span>
										</span>
									</div>
									{#if idx !== visibleHistory.length - 1}
										<div
											class="w-[0.5px] ml-[6.5px] h-[calc(100%-14px)] bg-gray-300 dark:bg-gray-700"
										/>
									{/if}
								</div>

								<StatusItem {status} done={true} />
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}
