<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
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
	import ThemeLogo from '$lib/components/common/ThemeLogo.svelte';
	import CloudArrowUp from '$lib/components/icons/CloudArrowUp.svelte';
	import Refresh from '$lib/components/icons/Refresh.svelte';
	import AdminSettingField from './AdminSettingField.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import { shouldPollUpdate, updateStageLabel } from '$lib/utils/updates';

	let info: UpdateInfo | null = null;
	let status: UpdateState = { stage: 'idle', active: false, updated_at: 0 };
	let loading = true;
	let refreshing = false;
	let deploying = false;
	let showDeployConfirm = false;
	let showReleaseNotes = false;
	let lastChecked = '';
	let pollTimer: ReturnType<typeof setTimeout> | null = null;
	let destroyed = false;

	$: buildHash = info?.build_hash ?? '';
	$: abbreviatedBuildHash = buildHash.length > 12 ? buildHash.slice(0, 8) : buildHash;
	$: updateFailed = status.stage === 'failed' || status.stage === 'rolled_back';
	$: currentVersion = info?.current ?? '-';
	$: targetVersion = status.target_version ?? info?.latest ?? currentVersion;
	$: stateLabel = loading
		? '版本状态'
		: status.active
			? updateStageLabel(status.stage)
			: updateFailed
				? '更新失败'
				: info?.update_available
					? '发现新版本'
					: '版本状态';
	$: stateTitle = loading
		? ''
		: status.active
			? `正在部署 ArtiChat v${targetVersion}`
			: updateFailed
				? `未能完成 ArtiChat v${targetVersion} 更新`
				: info?.update_available
					? `ArtiChat v${info.latest} 已可用`
					: `当前版本 v${currentVersion}`;
	$: stateDescription = loading
		? ''
		: status.active
			? (status.message ?? '更新完成后服务会自动恢复。')
			: updateFailed
				? (status.error ?? status.message ?? '当前版本已保留，服务仍可正常使用。')
				: info?.update_available
					? '有新的稳定版本可供部署。更新前会自动备份数据，服务将短暂重启。'
					: (info?.error ?? '当前版本已是最新。');

	const errorText = (error: unknown) => {
		if (error && typeof error === 'object' && 'detail' in error) {
			return String(error.detail);
		}
		return String(error);
	};

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
		lastChecked = '刚刚';
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

	const refresh = async () => {
		if (refreshing || status.active) return;
		refreshing = true;
		showReleaseNotes = false;
		await loadInfo(true);
		await loadStatus();
		schedulePolling();
		refreshing = false;
	};

	const confirmDeploy = async () => {
		if (!info?.latest || deploying) return;
		deploying = true;
		const accepted = await deployUpdate(localStorage.token, info.latest).catch((error) => {
			toast.error(errorText(error));
			return null;
		});
		if (accepted) {
			status = accepted;
			if (info) info = { ...info, status: accepted };
			toast.success('更新任务已提交。');
			schedulePolling();
		}
		deploying = false;
	};

	onMount(async () => {
		await loadInfo();
		await loadStatus(false);
		loading = false;
		schedulePolling();
	});

	onDestroy(() => {
		destroyed = true;
		clearPolling();
	});
</script>

<div class="flex flex-col gap-3">
	<AdminSettingRow
		label="ArtiChat"
		description={loading
			? '正在检查更新...'
			: `当前版本 v${currentVersion}${abbreviatedBuildHash ? ` (${abbreviatedBuildHash})` : ''}`}
	>
		<div class="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
			<ThemeLogo kind="mark" className="size-6 object-contain" alt="ArtiChat" />
			<span class="size-2 rounded-full bg-green-500" aria-hidden="true"></span>
			<span>运行正常</span>
		</div>
	</AdminSettingRow>

	{#if loading}
		<div
			class="flex min-h-16 items-center justify-center border-y border-gray-100 py-4 text-gray-400 dark:border-gray-850"
		>
			<Spinner className="size-5" />
		</div>
	{:else if info}
		<AdminSettingField label={stateLabel} description={stateDescription}>
			<div class="flex flex-col gap-2">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div class="text-sm font-medium {updateFailed ? 'text-red-700 dark:text-red-300' : ''}">
						{stateTitle}
					</div>
					<div class="flex w-full items-center gap-2 sm:w-auto">
						<button
							type="button"
							class="flex h-7 flex-1 items-center justify-center gap-1.5 rounded-lg border border-gray-200 px-2.5 text-[0.6875rem] font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-default disabled:opacity-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900 sm:flex-none"
							disabled={refreshing || status.active}
							on:click={refresh}
						>
							{#if refreshing}
								<Spinner className="size-3.5" />
							{:else}
								<Refresh className="size-3.5" />
							{/if}
							检查更新
						</button>

						{#if info.update_available && info.deployment_enabled && !status.active}
							<button
								type="button"
								class="flex h-7 flex-1 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-2.5 text-[0.6875rem] font-medium text-white transition hover:bg-gray-800 disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white sm:flex-none"
								disabled={deploying}
								on:click={() => (showDeployConfirm = true)}
							>
								{#if deploying}
									<Spinner className="size-3.5" />
								{:else}
									<CloudArrowUp className="size-3.5" />
								{/if}
								{updateFailed ? '重试更新' : '立即更新'}
							</button>
						{/if}
					</div>
				</div>

				{#if status.active}
					<div class="h-1.5 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-850">
						<div
							class="update-progress h-full w-3/5 rounded-full bg-gray-900 dark:bg-gray-100"
						></div>
					</div>
				{:else if info.update_available && !info.deployment_enabled}
					<div class="text-[0.6875rem] text-gray-400 dark:text-gray-600">未配置自动部署</div>
				{/if}
			</div>
		</AdminSettingField>

		{#if showReleaseNotes && info.release?.body}
			<AdminSettingField label="版本说明">
				<div
					class="max-h-48 overflow-y-auto whitespace-pre-wrap border-t border-gray-100 pt-3 text-xs leading-5 text-gray-600 dark:border-gray-850 dark:text-gray-300"
				>
					{info.release.body}
				</div>
			</AdminSettingField>
		{/if}
	{/if}

	<div
		class="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-2 text-[0.6875rem] text-gray-400 dark:border-gray-850"
	>
		<span>{lastChecked ? `上次检查：${lastChecked}` : '尚未完成版本检查'}</span>
		{#if info?.release?.body}
			<button
				type="button"
				class="font-medium text-gray-700 transition hover:text-black dark:text-gray-300 dark:hover:text-white"
				on:click={() => (showReleaseNotes = !showReleaseNotes)}
			>
				{showReleaseNotes ? '收起版本说明' : '查看版本说明'}
			</button>
		{/if}
	</div>
</div>

<ConfirmDialog
	bind:show={showDeployConfirm}
	title="确认更新"
	message="ArtiChat 将短暂重启，部署前会自动备份服务器数据。"
	confirmLabel="立即更新"
	on:confirm={confirmDeploy}
/>

<style>
	.update-progress {
		animation: update-progress 1.5s ease-in-out infinite alternate;
	}

	@keyframes update-progress {
		from {
			transform: translateX(-35%);
		}
		to {
			transform: translateX(70%);
		}
	}
</style>
