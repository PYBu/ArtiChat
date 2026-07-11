<script lang="ts">
	import { getContext, onDestroy, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		deployUpdate,
		getUpdateInfo,
		getUpdateStatus,
		type UpdateInfo,
		type UpdateState
	} from '$lib/apis/updates';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import CloudArrowUp from '$lib/components/icons/CloudArrowUp.svelte';
	import Refresh from '$lib/components/icons/Refresh.svelte';
	import { shouldPollUpdate, updateStageLabel } from '$lib/utils/updates';

	const i18n = getContext('i18n');

	let info: UpdateInfo | null = null;
	let status: UpdateState = { stage: 'idle', active: false, updated_at: 0 };
	let loading = true;
	let refreshing = false;
	let deploying = false;
	let showDeployConfirm = false;
	let pollTimer: ReturnType<typeof setTimeout> | null = null;
	let destroyed = false;

	$: buildHash = info?.build_hash ?? '';
	$: abbreviatedBuildHash = buildHash.length > 12 ? buildHash.slice(0, 8) : buildHash;

	const errorText = (error: any) => error?.detail ?? `${error}`;

	const clearPolling = () => {
		if (pollTimer) {
			clearTimeout(pollTimer);
			pollTimer = null;
		}
	};

	const schedulePolling = () => {
		clearPolling();
		if (!destroyed && shouldPollUpdate(status)) {
			pollTimer = setTimeout(pollStatus, 3000);
		}
	};

	const loadInfo = async (force = false, showErrors = true) => {
		const nextInfo = await getUpdateInfo(localStorage.token, force).catch((error) => {
			if (showErrors) toast.error(errorText(error));
			return null;
		});
		if (!nextInfo || destroyed) return null;

		info = nextInfo;
		status = nextInfo.status;
		if (nextInfo.error && showErrors) toast.error(nextInfo.error);
		return nextInfo;
	};

	const loadStatus = async (showErrors = true) => {
		const nextStatus = await getUpdateStatus(localStorage.token).catch((error) => {
			if (showErrors && status.stage !== 'restarting') toast.error(errorText(error));
			return null;
		});
		if (!nextStatus || destroyed) return null;

		status = nextStatus;
		if (info) info = { ...info, status: nextStatus };
		return nextStatus;
	};

	async function pollStatus() {
		const nextStatus = await loadStatus(status.stage !== 'restarting');
		if (destroyed) return;

		if (nextStatus && !shouldPollUpdate(nextStatus)) {
			await loadInfo(true, false);
		}
		schedulePolling();
	}

	const startPolling = () => {
		schedulePolling();
	};

	const refresh = async () => {
		if (refreshing) return;
		refreshing = true;
		await loadInfo(true);
		await loadStatus();
		startPolling();
		refreshing = false;
	};

	const confirmDeploy = async () => {
		if (!info?.latest || deploying) return;
		deploying = true;
		const accepted = await deployUpdate(localStorage.token, info.latest).catch((error) => {
			toast.error(error?.detail ?? `${error}`);
			return null;
		});
		if (accepted) {
			status = accepted;
			if (info) info = { ...info, status: accepted };
			toast.success('更新任务已提交。');
			startPolling();
		}
		deploying = false;
	};

	onMount(async () => {
		await loadInfo();
		await loadStatus(false);
		loading = false;
		startPolling();
	});

	onDestroy(() => {
		destroyed = true;
		clearPolling();
	});
</script>

<div class="border-b border-gray-100 dark:border-gray-850 pb-3">
	<div class="flex items-start justify-between gap-3">
		<div class="min-w-0">
			<div class="text-xs font-medium">{$i18n.t('Version')}</div>
			<div class="mt-1 text-xs text-gray-500 dark:text-gray-400">
				{#if loading}
					{$i18n.t('Checking for updates...')}
				{:else}
					{$i18n.t('Running version')}: {info?.display_version ?? info?.current ?? '-'}
					{#if abbreviatedBuildHash}
						<span class="ml-1 font-mono">({abbreviatedBuildHash})</span>
					{/if}
				{/if}
			</div>
		</div>

		<Tooltip content={$i18n.t('Check for updates')}>
			<button
				type="button"
				class="size-8 shrink-0 flex items-center justify-center rounded-lg text-gray-500 hover:text-gray-800 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-100 dark:hover:bg-gray-850 transition disabled:opacity-50"
				aria-label={$i18n.t('Check for updates')}
				disabled={refreshing}
				on:click={refresh}
			>
				{#if refreshing}
					<Spinner className="size-4" />
				{:else}
					<Refresh className="size-4" />
				{/if}
			</button>
		</Tooltip>
	</div>

	{#if !loading && info}
		<div class="mt-3 flex flex-col gap-3">
			<div class="flex items-center justify-between gap-3 text-xs">
				<div class="text-gray-500 dark:text-gray-400">{updateStageLabel(status.stage)}</div>
				{#if info.update_available}
					<div class="font-medium text-blue-600 dark:text-blue-400">v{info.latest}</div>
				{:else}
					<div class="text-gray-500 dark:text-gray-400">{$i18n.t('(latest)')}</div>
				{/if}
			</div>

			{#if info.release?.body}
				<div>
					<div class="text-xs font-medium mb-1">{$i18n.t('Release notes')}</div>
					<div
						class="max-h-36 overflow-y-auto whitespace-pre-wrap text-xs leading-5 text-gray-500 dark:text-gray-400"
					>
						{info.release.body}
					</div>
				</div>
			{/if}

			<div class="flex items-center justify-end">
				{#if info.update_available && info.deployment_enabled && !status.active}
					<button
						type="button"
						class="h-8 px-3 flex items-center gap-1.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-white dark:bg-gray-100 dark:hover:bg-white dark:text-gray-900 text-xs font-medium transition disabled:opacity-50"
						disabled={deploying}
						on:click={() => (showDeployConfirm = true)}
					>
						{#if deploying}
							<Spinner className="size-4" />
						{:else}
							<CloudArrowUp className="size-4" />
						{/if}
						{$i18n.t('Deploy update')}
					</button>
				{:else if info.update_available && !info.deployment_enabled}
					<div class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('Deployment is not configured')}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>

<ConfirmDialog
	bind:show={showDeployConfirm}
	title={$i18n.t('Confirm deployment')}
	message={$i18n.t(
		'ArtiChat will briefly restart. Server data will be backed up before deployment.'
	)}
	confirmLabel={$i18n.t('Deploy update')}
	on:confirm={confirmDeploy}
/>
