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

<div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800">
	<div class="flex min-h-[86px] items-center justify-between gap-4 px-5 py-4">
		<div class="flex min-w-0 items-center gap-3">
			<div
				class="flex size-11 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900"
			>
				<ThemeLogo kind="mark" className="size-7 object-contain" alt="ArtiChat" />
			</div>
			<div class="min-w-0">
				<div class="text-sm font-semibold">ArtiChat</div>
				<div class="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
					{#if loading}
						正在检查更新...
					{:else}
						当前版本 v{currentVersion}
						{#if abbreviatedBuildHash}
							<span class="ml-1 font-mono">({abbreviatedBuildHash})</span>
						{/if}
					{/if}
				</div>
			</div>
		</div>

		<div class="flex shrink-0 items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
			<span class="size-2 rounded-full bg-green-500 ring-4 ring-green-100 dark:ring-green-950"
			></span>
			<span>运行正常</span>
		</div>
	</div>

	<div
		class="border-t border-gray-200 bg-gray-50/60 px-5 py-5 dark:border-gray-800 dark:bg-gray-900/40"
	>
		{#if loading}
			<div class="flex min-h-[72px] items-center justify-center text-gray-400">
				<Spinner className="size-5" />
			</div>
		{:else if info}
			<div class="grid grid-cols-1 items-center gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-6">
				<div class="min-w-0">
					{#if status.active}
						<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
							{updateStageLabel(status.stage)}
						</div>
						<div class="mt-1 text-sm font-semibold">正在部署 ArtiChat v{targetVersion}</div>
						<div class="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
							{status.message ?? '更新完成后服务会自动恢复。'}
						</div>
						<div class="mt-4 h-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-800">
							<div
								class="update-progress h-full w-3/5 rounded-full bg-gray-900 dark:bg-gray-100"
							></div>
						</div>
					{:else if updateFailed}
						<div class="text-xs font-medium text-red-600 dark:text-red-400">更新失败</div>
						<div class="mt-1 text-sm font-semibold text-red-700 dark:text-red-300">
							未能完成 ArtiChat v{targetVersion} 更新
						</div>
						<div class="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
							{status.error ?? status.message ?? '当前版本已保留，服务仍可正常使用。'}
						</div>
					{:else if info.update_available}
						<div class="text-xs font-medium text-gray-500 dark:text-gray-400">发现新版本</div>
						<div class="mt-1 text-sm font-semibold">ArtiChat v{info.latest} 已可用</div>
						<div class="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
							有新的稳定版本可供部署。更新前会自动备份数据，服务将短暂重启。
						</div>
					{:else}
						<div class="text-xs font-medium text-gray-500 dark:text-gray-400">版本状态</div>
						<div class="mt-1 text-sm font-semibold">当前版本 v{currentVersion}</div>
						{#if info.error}
							<div class="mt-1 text-xs leading-5 text-red-600 dark:text-red-400">
								{info.error}
							</div>
						{/if}
					{/if}
				</div>

				<div class="flex w-full items-center gap-2 sm:w-auto">
					<button
						type="button"
						class="flex h-9 flex-1 items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-3 text-xs font-medium text-gray-800 transition hover:bg-gray-100 disabled:cursor-default disabled:opacity-50 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-100 dark:hover:bg-gray-800 sm:flex-none"
						disabled={refreshing || status.active}
						on:click={refresh}
					>
						{#if refreshing}
							<Spinner className="size-4" />
						{:else}
							<Refresh className="size-4" />
						{/if}
						检查更新
					</button>

					{#if info.update_available && info.deployment_enabled && !status.active}
						<button
							type="button"
							class="flex h-9 flex-1 items-center justify-center gap-2 rounded-lg bg-gray-900 px-3 text-xs font-medium text-white transition hover:bg-gray-800 disabled:opacity-50 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white sm:flex-none"
							disabled={deploying}
							on:click={() => (showDeployConfirm = true)}
						>
							{#if deploying}
								<Spinner className="size-4" />
							{:else}
								<CloudArrowUp className="size-4" />
							{/if}
							{updateFailed ? '重试更新' : '立即更新'}
						</button>
					{/if}
				</div>
			</div>

			{#if info.update_available && !info.deployment_enabled && !status.active}
				<div class="mt-3 text-xs text-gray-500 dark:text-gray-400">未配置自动部署</div>
			{/if}

			{#if showReleaseNotes && info.release?.body}
				<div
					class="mt-4 max-h-48 overflow-y-auto whitespace-pre-wrap border-t border-gray-200 pt-4 text-xs leading-5 text-gray-600 dark:border-gray-800 dark:text-gray-300"
				>
					{info.release.body}
				</div>
			{/if}
		{/if}
	</div>

	<div
		class="flex min-h-11 flex-col items-start justify-between gap-2 border-t border-gray-200 px-5 py-3 text-[11px] text-gray-400 dark:border-gray-800 sm:flex-row sm:items-center"
	>
		<span>{lastChecked ? `上次检查：${lastChecked}` : '尚未完成版本检查'}</span>
		{#if info?.release?.body}
			<button
				type="button"
				class="font-medium text-gray-700 hover:text-black dark:text-gray-300 dark:hover:text-white"
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
