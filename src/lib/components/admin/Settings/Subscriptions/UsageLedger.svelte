<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import ChevronLeft from '$lib/components/icons/ChevronLeft.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import Download from '$lib/components/icons/Download.svelte';
	import Refresh from '$lib/components/icons/Refresh.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import { searchUsers } from '$lib/apis/users';
	import {
		exportAdminSubscriptionUsage,
		getAdminSubscriptionLedger,
		getAdminSubscriptionUsage,
		getAdminSubscriptionUsageOverview,
		type AdminUsageFilters,
		type SubscriptionLedgerEntry,
		type SubscriptionUsageOverview,
		type SubscriptionUsageSummary,
		type UserSummary
	} from '$lib/apis/subscriptions';

	type TimePreset = 'all' | 'today' | '7d' | '30d' | 'since_registration' | 'custom';
	type DetailTab = 'requests' | 'balances';

	const PAGE_SIZE = 25;
	const MODEL_COLORS = [
		'#111827',
		'#2563eb',
		'#0f766e',
		'#d97706',
		'#be123c',
		'#7c3aed',
		'#0891b2',
		'#65a30d',
		'#c2410c',
		'#4b5563'
	];

	const emptyUsage = (): SubscriptionUsageSummary => ({
		items: [],
		total_item_count: 0,
		total_cost_micros: 0,
		total_plan_cost_micros: 0,
		total_check_cost_micros: 0,
		total_unpaid_cost_micros: 0,
		total_input_tokens: 0,
		total_output_tokens: 0,
		total_cache_creation_tokens: 0,
		total_cache_read_tokens: 0,
		total_tokens: 0,
		total_request_count: 0,
		media_totals: [],
		model_totals: []
	});
	const emptyOverview = (): SubscriptionUsageOverview => ({
		...emptyUsage(),
		generated_at: 0,
		recent_30d_start_at: 0,
		recent_30d_request_count: 0
	});

	let overview = emptyOverview();
	let usage = emptyUsage();
	let ledger: SubscriptionLedgerEntry[] = [];
	let ledgerTotal = 0;
	let loadingOverview = true;
	let loadingDetails = true;
	let exporting = false;
	let selectedUser: UserSummary | null = null;
	let userQuery = '';
	let userResults: UserSummary[] = [];
	let searchingUsers = false;
	let userSearchComplete = false;
	let statusFilter = '';
	let usageTypeFilter = '';
	let mediaUnitFilter = '';
	let timePreset: TimePreset = 'all';
	let startDate = '';
	let endDate = '';
	let activeTab: DetailTab = 'requests';
	let requestPage = 1;
	let balancePage = 1;
	let userSearchTimer: ReturnType<typeof setTimeout>;
	let userSearchSequence = 0;
	let detailsSequence = 0;

	const formatChatpoint = (micros?: number | null) =>
		((micros ?? 0) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 4 });
	const formatSignedChatpoint = (micros?: number | null) => {
		const value = (micros ?? 0) / 1_000_000;
		return `${value > 0 ? '+' : ''}${value.toLocaleString(undefined, { maximumFractionDigits: 4 })}`;
	};
	const formatNumber = (value?: number | null) => (value ?? 0).toLocaleString();
	const formatCompact = (value?: number | null) =>
		new Intl.NumberFormat('zh-CN', { notation: 'compact', maximumFractionDigits: 1 }).format(
			value ?? 0
		);
	const formatDate = (value?: number | null) =>
		value ? new Date(value * 1000).toLocaleString() : '-';
	const userLabel = (item: { user?: UserSummary | null; user_id?: string }) =>
		item.user?.email ?? item.user?.username ?? item.user?.name ?? item.user_id ?? '-';
	const selectedUserLabel = (user: UserSummary) =>
		user.email || user.username || user.name || user.id;
	const dateToTimestamp = (value: string, endOfDay = false) => {
		if (!value) return undefined;
		const date = new Date(`${value}T${endOfDay ? '23:59:59.999' : '00:00:00'}`);
		return Math.floor(date.getTime() / 1000);
	};
	const statusLabel = (status: string) => {
		if (status === 'billed') return '已计费';
		if (status === 'partially_billed') return '部分计费';
		if (status === 'unlimited') return '无限使用';
		if (status === 'admin_bypass') return '管理员绕过';
		if (status === 'missing_usage') return '缺少用量';
		if (status === 'failed') return '生成失败（未计费）';
		return status;
	};
	const eventLabel = (eventType: string) => {
		if (eventType === 'usage_debit') return '模型扣费';
		if (eventType === 'reservation_settlement') return '模型结算';
		if (eventType === 'redemption') return '兑换码入账';
		if (eventType === 'gift_claim') return '领取礼品';
		if (eventType === 'admin_adjustment') return '管理员调整';
		if (eventType === 'period_reset') return '周期重置';
		return eventType;
	};
	const sourceLabel = (entry: SubscriptionLedgerEntry) => {
		const type = entry.reference_type;
		if (!type && !entry.reference_id) return '-';
		const label =
			type === 'subscription_reservation'
				? '模型请求'
				: type === 'redemption'
					? '兑换码'
					: type === 'gift_grant'
						? '礼品卡'
						: type || '来源';
		return entry.reference_id ? `${label} · ${entry.reference_id}` : label;
	};

	const getTimeRange = () => {
		const now = new Date();
		const nowSeconds = Math.floor(now.getTime() / 1000);
		if (timePreset === 'today') {
			const start = new Date(now);
			start.setHours(0, 0, 0, 0);
			return { startAt: Math.floor(start.getTime() / 1000), endAt: nowSeconds };
		}
		if (timePreset === '7d') return { startAt: nowSeconds - 7 * 24 * 60 * 60, endAt: nowSeconds };
		if (timePreset === '30d') return { startAt: nowSeconds - 30 * 24 * 60 * 60, endAt: nowSeconds };
		if (timePreset === 'since_registration' && selectedUser?.created_at)
			return { startAt: selectedUser.created_at, endAt: nowSeconds };
		if (timePreset === 'custom')
			return {
				startAt: dateToTimestamp(startDate),
				endAt: dateToTimestamp(endDate, true)
			};
		return {};
	};

	const currentFilters = (): AdminUsageFilters => ({
		userId: selectedUser?.id,
		status: statusFilter || undefined,
		usageType: usageTypeFilter || undefined,
		mediaUnit: mediaUnitFilter || undefined,
		...getTimeRange()
	});

	const loadOverview = async () => {
		loadingOverview = true;
		try {
			overview = await getAdminSubscriptionUsageOverview(localStorage.token);
		} catch (error) {
			toast.error(`${error}`);
			overview = emptyOverview();
		} finally {
			loadingOverview = false;
		}
	};

	const loadDetails = async () => {
		const sequence = ++detailsSequence;
		loadingDetails = true;
		const filters = currentFilters();
		try {
			const [usageResponse, ledgerResponse] = await Promise.all([
				getAdminSubscriptionUsage(localStorage.token, {
					...filters,
					limit: PAGE_SIZE,
					offset: (requestPage - 1) * PAGE_SIZE
				}),
				getAdminSubscriptionLedger(localStorage.token, {
					userId: filters.userId,
					startAt: filters.startAt,
					endAt: filters.endAt,
					limit: PAGE_SIZE,
					offset: (balancePage - 1) * PAGE_SIZE
				})
			]);
			if (sequence !== detailsSequence) return;
			usage = usageResponse;
			ledger = ledgerResponse.items;
			ledgerTotal = ledgerResponse.total_item_count;
		} catch (error) {
			if (sequence !== detailsSequence) return;
			toast.error(`${error}`);
			usage = emptyUsage();
			ledger = [];
			ledgerTotal = 0;
		} finally {
			if (sequence === detailsSequence) loadingDetails = false;
		}
	};

	const refreshAll = () => Promise.all([loadOverview(), loadDetails()]);
	const applyFilters = () => {
		requestPage = 1;
		balancePage = 1;
		void loadDetails();
	};
	const resetFilters = () => {
		selectedUser = null;
		userQuery = '';
		userResults = [];
		statusFilter = '';
		usageTypeFilter = '';
		mediaUnitFilter = '';
		timePreset = 'all';
		startDate = '';
		endDate = '';
		applyFilters();
	};

	const searchLedgerUsers = async () => {
		const query = userQuery.trim();
		const sequence = ++userSearchSequence;
		if (!query || (selectedUser && query === selectedUserLabel(selectedUser))) {
			userResults = [];
			searchingUsers = false;
			userSearchComplete = false;
			return;
		}
		searchingUsers = true;
		userSearchComplete = false;
		const response = await searchUsers(localStorage.token, query, 'name', 'asc', 1).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);
		if (sequence !== userSearchSequence) return;
		userResults = (response?.users ?? []).slice(0, 8);
		searchingUsers = false;
		userSearchComplete = true;
	};
	const scheduleUserSearch = () => {
		clearTimeout(userSearchTimer);
		if (selectedUser && userQuery !== selectedUserLabel(selectedUser)) selectedUser = null;
		userSearchTimer = setTimeout(searchLedgerUsers, 250);
	};
	const selectUser = (user: UserSummary) => {
		selectedUser = user;
		userQuery = selectedUserLabel(user);
		userResults = [];
		userSearchComplete = false;
		userSearchSequence += 1;
	};
	const clearUser = () => {
		selectedUser = null;
		userQuery = '';
		userResults = [];
		if (timePreset === 'since_registration') timePreset = 'all';
	};

	const changeRequestPage = (nextPage: number) => {
		requestPage = nextPage;
		void loadDetails();
	};
	const changeBalancePage = (nextPage: number) => {
		balancePage = nextPage;
		void loadDetails();
	};
	const exportCsv = async () => {
		exporting = true;
		try {
			const blob = await exportAdminSubscriptionUsage(
				localStorage.token,
				activeTab,
				currentFilters()
			);
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = `usage-ledger-${activeTab}.csv`;
			link.click();
			URL.revokeObjectURL(url);
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			exporting = false;
		}
	};

	const buildModelSegments = (items: SubscriptionUsageOverview['model_totals']) => {
		const used = items.filter((item) => item.total_tokens > 0);
		const total = used.reduce((sum, item) => sum + item.total_tokens, 0);
		let cursor = 0;
		return used.map((item, index) => {
			const percent = total ? (item.total_tokens / total) * 100 : 0;
			const segment = {
				...item,
				color: MODEL_COLORS[index % MODEL_COLORS.length],
				percent,
				start: cursor,
				end: cursor + percent
			};
			cursor += percent;
			return segment;
		});
	};

	$: modelSegments = buildModelSegments(overview.model_totals ?? []);
	$: modelGradient = modelSegments.length
		? `conic-gradient(${modelSegments.map((item) => `${item.color} ${item.start}% ${item.end}%`).join(', ')})`
		: 'conic-gradient(#e5e7eb 0 100%)';
	$: deductedTotal = overview.total_plan_cost_micros + overview.total_check_cost_micros;
	$: planPercent = deductedTotal ? (overview.total_plan_cost_micros / deductedTotal) * 100 : 0;
	$: balanceGradient = deductedTotal
		? `conic-gradient(#111827 0 ${planPercent}%, #0d9488 ${planPercent}% 100%)`
		: 'conic-gradient(#e5e7eb 0 100%)';
	$: tokenMaximum = Math.max(
		usage.total_input_tokens,
		usage.total_output_tokens,
		usage.total_cache_creation_tokens,
		usage.total_cache_read_tokens,
		1
	);
	$: requestPages = Math.max(1, Math.ceil(usage.total_item_count / PAGE_SIZE));
	$: balancePages = Math.max(1, Math.ceil(ledgerTotal / PAGE_SIZE));
	$: overviewMetrics = [
		{ label: '总请求', value: formatNumber(overview.total_request_count), note: '全部历史' },
		{
			label: '近期请求',
			value: formatNumber(overview.recent_30d_request_count),
			note: '最近 30 天'
		},
		{
			label: '总 Plan 消耗',
			value: formatChatpoint(overview.total_plan_cost_micros),
			note: 'Chatpoint'
		},
		{
			label: '总充值消耗',
			value: formatChatpoint(overview.total_check_cost_micros),
			note: 'Chatpoint'
		},
		{
			label: '总输入 Token',
			value: formatCompact(overview.total_input_tokens),
			note: formatNumber(overview.total_input_tokens)
		},
		{
			label: '总输出 Token',
			value: formatCompact(overview.total_output_tokens),
			note: formatNumber(overview.total_output_tokens)
		}
	];

	onMount(() => void refreshAll());
	onDestroy(() => clearTimeout(userSearchTimer));
</script>

<div class="usage-ledger min-w-0 space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<div class="text-sm font-medium">平台累计</div>
			<div class="mt-0.5 text-[11px] text-gray-500">统计保留至今的权威用量记录</div>
		</div>
		<div class="flex items-center gap-2">
			<button
				type="button"
				class="inline-flex size-8 items-center justify-center rounded-lg border border-gray-100/70 text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-white/[0.08] dark:text-gray-300 dark:hover:bg-white/[0.05]"
				title="刷新账本"
				aria-label="刷新账本"
				disabled={loadingOverview || loadingDetails}
				on:click={() => void refreshAll()}
			>
				<Refresh
					className={`size-3.5 ${loadingOverview || loadingDetails ? 'animate-spin' : ''}`}
					strokeWidth="2"
				/>
			</button>
			<button
				type="button"
				class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-gray-100/70 px-3 text-xs font-medium hover:bg-gray-50 disabled:opacity-50 dark:border-white/[0.08] dark:hover:bg-white/[0.05]"
				disabled={exporting}
				on:click={exportCsv}
			>
				<Download className="size-3.5" strokeWidth="2" />
				{exporting ? '导出中' : '导出 CSV'}
			</button>
		</div>
	</div>

	<div
		class="grid grid-cols-2 overflow-hidden rounded-lg border border-gray-100/70 lg:grid-cols-3 xl:grid-cols-6 dark:border-white/[0.08]"
	>
		{#each overviewMetrics as metric}
			<div
				class="min-w-0 border-b border-gray-100/70 p-3 last:border-b-0 sm:border-r lg:border-b-0 dark:border-white/[0.08]"
			>
				<div class="text-[11px] text-gray-500">{metric.label}</div>
				<div class="mt-1 truncate text-lg font-medium tabular-nums">
					{loadingOverview ? '-' : metric.value}
				</div>
				<div class="mt-0.5 truncate text-[10px] text-gray-400">{metric.note}</div>
			</div>
		{/each}
	</div>

	<div class="grid min-w-0 gap-3 lg:grid-cols-2">
		<section class="min-w-0 rounded-lg border border-gray-100/70 p-4 dark:border-white/[0.08]">
			<div class="mb-4 flex items-center justify-between gap-3">
				<div class="text-sm font-medium">总模型占比用量</div>
				<div class="text-[11px] text-gray-500">{formatCompact(overview.total_tokens)} Token</div>
			</div>
			<div class="grid items-center gap-4 sm:grid-cols-[11rem_minmax(0,1fr)]">
				<div
					class="mx-auto flex size-40 items-center justify-center rounded-full"
					style={`background: ${modelGradient}`}
				>
					<div
						class="flex size-28 flex-col items-center justify-center rounded-full bg-white text-center dark:bg-gray-900"
					>
						<div class="text-xl font-medium tabular-nums">
							{formatCompact(overview.total_tokens)}
						</div>
						<div class="text-[10px] text-gray-500">总 Token</div>
					</div>
				</div>
				<div class="max-h-44 min-w-0 space-y-2 overflow-y-auto pr-1">
					{#if modelSegments.length}
						{#each modelSegments as model}
							<div
								class="grid min-w-0 grid-cols-[0.5rem_minmax(0,1fr)_auto] items-center gap-2 text-[11px]"
							>
								<span class="size-2 rounded-sm" style={`background: ${model.color}`}></span>
								<span class="truncate" title={model.model_id}>{model.model_id}</span>
								<span class="tabular-nums text-gray-500">{model.percent.toFixed(1)}%</span>
							</div>
						{/each}
					{:else}
						<div class="text-xs text-gray-500">暂无模型用量</div>
					{/if}
				</div>
			</div>
		</section>

		<section class="min-w-0 rounded-lg border border-gray-100/70 p-4 dark:border-white/[0.08]">
			<div class="mb-4 flex items-center justify-between gap-3">
				<div class="text-sm font-medium">Plan 与充值额度</div>
				<div class="text-[11px] text-gray-500">实际扣费</div>
			</div>
			<div class="grid items-center gap-4 sm:grid-cols-[11rem_minmax(0,1fr)]">
				<div
					class="mx-auto flex size-40 items-center justify-center rounded-full"
					style={`background: ${balanceGradient}`}
				>
					<div
						class="flex size-28 flex-col items-center justify-center rounded-full bg-white text-center dark:bg-gray-900"
					>
						<div class="text-xl font-medium tabular-nums">{formatChatpoint(deductedTotal)}</div>
						<div class="text-[10px] text-gray-500">已扣 CP</div>
					</div>
				</div>
				<div class="space-y-3 text-xs">
					<div class="grid grid-cols-[0.5rem_1fr_auto] items-center gap-2">
						<span class="size-2 rounded-sm bg-gray-900 dark:bg-gray-100"></span><span>Plan</span>
						<span class="tabular-nums">{deductedTotal ? planPercent.toFixed(1) : '0.0'}%</span>
					</div>
					<div class="grid grid-cols-[0.5rem_1fr_auto] items-center gap-2">
						<span class="size-2 rounded-sm bg-teal-600"></span><span>充值额度</span>
						<span class="tabular-nums"
							>{deductedTotal ? (100 - planPercent).toFixed(1) : '0.0'}%</span
						>
					</div>
					<div
						class="border-t border-gray-100 pt-3 text-[11px] text-gray-500 dark:border-white/[0.08]"
					>
						未扣欠费 {formatChatpoint(overview.total_unpaid_cost_micros)} CP
					</div>
				</div>
			</div>
		</section>

		<section class="min-w-0 rounded-lg border border-gray-100/70 p-4 dark:border-white/[0.08]">
			<div class="mb-3 text-sm font-medium">媒体用量</div>
			{#if usage.media_totals.length}
				<dl class="divide-y divide-gray-100 text-xs dark:divide-white/[0.08]">
					{#each usage.media_totals as media}
						<div class="flex items-center justify-between gap-3 py-2">
							<dt class="text-gray-500">
								{media.usage_type === 'video' ? '视频' : '图片'}
								· {media.media_unit === 'second' ? '秒' : '张'}
							</dt>
							<dd class="tabular-nums">{formatNumber(media.units)}</dd>
						</div>
					{/each}
				</dl>
			{:else}
				<div class="text-xs text-gray-500">暂无媒体用量</div>
			{/if}
		</section>
	</div>

	<section class="min-w-0 border-t border-gray-100/70 pt-4 dark:border-white/[0.08]">
		<div class="mb-3 flex items-center justify-between gap-3">
			<div class="text-sm font-medium">筛选视图</div>
			<button
				type="button"
				class="text-[11px] text-gray-500 hover:text-gray-900 dark:hover:text-white"
				on:click={resetFilters}>重置</button
			>
		</div>
		<div class="grid min-w-0 gap-2 md:grid-cols-[minmax(13rem,1fr)_8rem_8rem_8rem_8rem_auto]">
			<div class="relative min-w-0">
				<Search
					className="pointer-events-none absolute left-2.5 top-2 size-3.5 text-gray-400"
					strokeWidth="2"
				/>
				<input
					class="h-8 w-full rounded-lg border border-gray-100/70 bg-gray-50/40 pl-8 pr-8 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.08] dark:bg-white/[0.03]"
					bind:value={userQuery}
					placeholder="搜索用户名或邮箱"
					on:input={scheduleUserSearch}
					on:focus={scheduleUserSearch}
				/>
				{#if selectedUser || userQuery}
					<button
						type="button"
						class="absolute right-1.5 top-1.5 inline-flex size-5 items-center justify-center rounded text-gray-400 hover:bg-gray-100 dark:hover:bg-white/[0.06]"
						title="清除用户"
						aria-label="清除用户"
						on:click={clearUser}
					>
						<XMark className="size-3.5" />
					</button>
				{/if}
				{#if searchingUsers || userResults.length || (userSearchComplete && userQuery && !selectedUser)}
					<div
						class="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-100 bg-white p-1 shadow-lg dark:border-gray-800 dark:bg-gray-900"
					>
						{#if searchingUsers}
							<div class="px-2 py-2 text-[11px] text-gray-500">搜索中...</div>
						{:else if userResults.length}
							{#each userResults as user (user.id)}
								<button
									type="button"
									class="block w-full rounded-md px-2 py-2 text-left hover:bg-gray-50 dark:hover:bg-white/[0.05]"
									on:click={() => selectUser(user)}
								>
									<div class="truncate text-xs">
										{user.name || user.username || user.email || user.id}
									</div>
									<div class="truncate text-[10px] text-gray-500">{user.email || user.id}</div>
								</button>
							{/each}
						{:else}
							<div class="px-2 py-2 text-[11px] text-gray-500">未找到用户</div>
						{/if}
					</div>
				{/if}
			</div>
			<select
				class="h-8 rounded-lg border border-gray-100/70 bg-gray-50/40 px-2 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.08] dark:bg-white/[0.03]"
				bind:value={statusFilter}
			>
				<option value="">全部计费状态</option>
				<option value="billed">已计费</option>
				<option value="partially_billed">部分计费</option>
				<option value="unlimited">无限使用</option>
				<option value="admin_bypass">管理员绕过</option>
				<option value="missing_usage">缺少用量</option>
			</select>
			<select
				class="h-8 rounded-lg border border-gray-100/70 bg-gray-50/40 px-2 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.08] dark:bg-white/[0.03]"
				bind:value={usageTypeFilter}
				aria-label="Media type"
			>
				<option value="">All types</option>
				<option value="chat">Chat</option>
				<option value="image">Image</option>
				<option value="video">Video</option>
			</select>
			<select
				class="h-8 rounded-lg border border-gray-100/70 bg-gray-50/40 px-2 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.08] dark:bg-white/[0.03]"
				bind:value={mediaUnitFilter}
				aria-label="Media unit"
			>
				<option value="">All units</option>
				<option value="image">Images</option>
				<option value="second">Seconds</option>
			</select>
			<select
				class="h-8 rounded-lg border border-gray-100/70 bg-gray-50/40 px-2 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.08] dark:bg-white/[0.03]"
				bind:value={timePreset}
			>
				<option value="all">全部时间</option>
				<option value="today">今天</option>
				<option value="7d">最近 7 天</option>
				<option value="30d">最近 30 天</option>
				<option value="since_registration" disabled={!selectedUser}>从注册至今</option>
				<option value="custom">自定义</option>
			</select>
			<button
				type="button"
				class="h-8 rounded-lg bg-black px-4 text-xs font-medium text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-100"
				on:click={applyFilters}>查询</button
			>
		</div>
		{#if timePreset === 'custom'}
			<div class="mt-2 grid gap-2 sm:max-w-xl sm:grid-cols-2">
				<label class="flex items-center gap-2 text-[11px] text-gray-500"
					><span class="w-8 shrink-0">开始</span><input
						type="date"
						class="h-8 min-w-0 flex-1 rounded-lg border border-gray-100/70 bg-gray-50/40 px-2 text-xs dark:border-white/[0.08] dark:bg-white/[0.03]"
						bind:value={startDate}
					/></label
				>
				<label class="flex items-center gap-2 text-[11px] text-gray-500"
					><span class="w-8 shrink-0">结束</span><input
						type="date"
						class="h-8 min-w-0 flex-1 rounded-lg border border-gray-100/70 bg-gray-50/40 px-2 text-xs dark:border-white/[0.08] dark:bg-white/[0.03]"
						bind:value={endDate}
					/></label
				>
			</div>
		{/if}
	</section>

	<div class="grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1.35fr)_minmax(16rem,0.65fr)]">
		<section class="min-w-0 rounded-lg border border-gray-100/70 p-4 dark:border-white/[0.08]">
			<div class="mb-4 flex items-center justify-between gap-3">
				<div class="text-sm font-medium">模型用量</div>
				<div class="text-[11px] text-gray-500">{formatCompact(usage.total_tokens)} Token</div>
			</div>
			<div class="space-y-3">
				{#each [{ label: '输入', value: usage.total_input_tokens, color: 'bg-blue-600' }, { label: '输出', value: usage.total_output_tokens, color: 'bg-teal-600' }, { label: '缓存创建', value: usage.total_cache_creation_tokens, color: 'bg-amber-500' }, { label: '缓存读取', value: usage.total_cache_read_tokens, color: 'bg-rose-500' }] as token}
					<div class="grid grid-cols-[4rem_minmax(0,1fr)_5.5rem] items-center gap-2 text-[11px]">
						<span class="text-gray-500">{token.label}</span>
						<div class="h-2 overflow-hidden rounded-sm bg-gray-100 dark:bg-white/[0.08]">
							<div
								class={`h-full ${token.color}`}
								style={`width: ${(token.value / tokenMaximum) * 100}%`}
							></div>
						</div>
						<span class="text-right tabular-nums">{formatCompact(token.value)}</span>
					</div>
				{/each}
			</div>
		</section>

		<section class="min-w-0 rounded-lg border border-gray-100/70 p-4 dark:border-white/[0.08]">
			<div class="mb-3 flex items-center justify-between gap-3">
				<div class="text-sm font-medium">扣费来源</div>
				<div class="text-[11px] text-gray-500">
					{formatChatpoint(usage.total_plan_cost_micros + usage.total_check_cost_micros)} CP
				</div>
			</div>
			<dl class="divide-y divide-gray-100 text-xs dark:divide-white/[0.08]">
				<div class="flex items-center justify-between gap-3 py-2">
					<dt class="text-gray-500">Plan Chatpoint</dt>
					<dd class="tabular-nums">{formatChatpoint(usage.total_plan_cost_micros)}</dd>
				</div>
				<div class="flex items-center justify-between gap-3 py-2">
					<dt class="text-gray-500">充值 Chatpoint</dt>
					<dd class="tabular-nums">{formatChatpoint(usage.total_check_cost_micros)}</dd>
				</div>
				<div class="flex items-center justify-between gap-3 py-2">
					<dt class="text-gray-500">未扣费用</dt>
					<dd class="tabular-nums">{formatChatpoint(usage.total_unpaid_cost_micros)}</dd>
				</div>
				<div class="flex items-center justify-between gap-3 py-2">
					<dt class="text-gray-500">平均每请求</dt>
					<dd class="tabular-nums">
						{formatChatpoint(
							usage.total_request_count
								? (usage.total_plan_cost_micros + usage.total_check_cost_micros) /
										usage.total_request_count
								: 0
						)}
					</dd>
				</div>
			</dl>
		</section>
	</div>

	<section class="min-w-0 border-t border-gray-100/70 pt-4 dark:border-white/[0.08]">
		<div class="mb-3 flex flex-wrap items-center justify-between gap-3">
			<div class="text-sm font-medium">账本明细</div>
			<div class="inline-flex rounded-lg bg-gray-50 p-1 dark:bg-white/[0.04]">
				<button
					type="button"
					class:bg-white={activeTab === 'requests'}
					class:shadow-sm={activeTab === 'requests'}
					class="rounded-md px-3 py-1.5 text-xs"
					on:click={() => (activeTab = 'requests')}>模型请求</button
				>
				<button
					type="button"
					class:bg-white={activeTab === 'balances'}
					class:shadow-sm={activeTab === 'balances'}
					class="rounded-md px-3 py-1.5 text-xs"
					on:click={() => (activeTab = 'balances')}>余额流水</button
				>
			</div>
		</div>

		{#if loadingDetails}
			<div
				class="rounded-lg border border-gray-100/70 p-6 text-center text-xs text-gray-500 dark:border-white/[0.08]"
			>
				加载中...
			</div>
		{:else if activeTab === 'requests'}
			{#if usage.items.length}
				<div
					class="max-w-full overflow-x-auto rounded-lg border border-gray-100/70 dark:border-white/[0.08]"
				>
					<table class="w-full min-w-[70rem] text-left text-[11px]">
						<thead class="bg-gray-50/70 text-gray-500 dark:bg-white/[0.03]"
							><tr
								>{#each ['时间', '用户', '类型', '模型', '用量', '输入', '输出', '创建缓存', '读取缓存', 'Plan CP', '充值 CP', '状态'] as heading}<th
										class="whitespace-nowrap px-3 py-2 font-medium">{heading}</th
									>{/each}</tr
							></thead
						>
						<tbody class="divide-y divide-gray-100 dark:divide-white/[0.06]">
							{#each usage.items as item (item.id)}
								<tr>
									<td class="whitespace-nowrap px-3 py-2">{formatDate(item.created_at)}</td>
									<td class="max-w-48 truncate px-3 py-2" title={userLabel(item)}>{userLabel(item)}</td>
									<td class="px-3 py-2">
										{item.usage_type === 'video' ? '视频' : item.usage_type === 'image' ? '图片' : '聊天'}
									</td>
									<td class="max-w-48 truncate px-3 py-2" title={item.model_id}>{item.model_id}</td>
									<td class="px-3 py-2 tabular-nums">
										{item.media_units != null
											? `${formatNumber(item.media_units)} ${item.media_unit === 'second' ? '秒' : '张'}`
											: '-'}
									</td>
									<td class="px-3 py-2 tabular-nums">{formatNumber(item.input_tokens)}</td>
									<td class="px-3 py-2 tabular-nums">{formatNumber(item.output_tokens)}</td>
									<td class="px-3 py-2 tabular-nums">{formatNumber(item.cache_creation_tokens)}</td>
									<td class="px-3 py-2 tabular-nums">{formatNumber(item.cache_read_tokens)}</td>
									<td class="px-3 py-2 tabular-nums">{formatChatpoint(item.plan_cost_micros)}</td>
									<td class="px-3 py-2 tabular-nums">{formatChatpoint(item.check_cost_micros)}</td>
									<td class="px-3 py-2">
										<span
											class:status-amber={item.status === 'partially_billed' || item.status === 'missing_usage'}
											class:status-green={item.status === 'billed'}
											class="status-badge">{statusLabel(item.status)}</span
										>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div
					class="rounded-lg border border-gray-100/70 px-3 py-6 text-center text-xs text-gray-500 dark:border-white/[0.08]"
				>
					暂无模型请求
				</div>
			{/if}
			<div class="mt-3 flex items-center justify-end gap-2 text-[11px]">
				<span class="mr-1 text-gray-500"
					>第 {requestPage} / {requestPages} 页 · {formatNumber(usage.total_item_count)} 条</span
				><button
					type="button"
					class="page-button"
					aria-label="模型请求上一页"
					title="上一页"
					disabled={requestPage <= 1}
					on:click={() => changeRequestPage(requestPage - 1)}
					><ChevronLeft className="size-3.5" strokeWidth="2" /></button
				><button
					type="button"
					class="page-button"
					aria-label="模型请求下一页"
					title="下一页"
					disabled={requestPage >= requestPages}
					on:click={() => changeRequestPage(requestPage + 1)}
					><ChevronRight className="size-3.5" strokeWidth="2" /></button
				>
			</div>
		{:else}
			{#if ledger.length}
				<div
					class="max-w-full overflow-x-auto rounded-lg border border-gray-100/70 dark:border-white/[0.08]"
				>
					<table class="w-full min-w-[64rem] text-left text-[11px]">
						<thead class="bg-gray-50/70 text-gray-500 dark:bg-white/[0.03]"
							><tr
								>{#each ['时间', '用户', '事件', '来源', 'Plan 变动', '充值变动', 'Plan 余额', '充值余额'] as heading}<th
										class="whitespace-nowrap px-3 py-2 font-medium">{heading}</th
									>{/each}</tr
							></thead
						>
						<tbody class="divide-y divide-gray-100 dark:divide-white/[0.06]">
							{#each ledger as entry (entry.id)}
								<tr
									><td class="whitespace-nowrap px-3 py-2">{formatDate(entry.created_at)}</td><td
										class="max-w-48 truncate px-3 py-2"
										title={userLabel(entry)}>{userLabel(entry)}</td
									><td class="px-3 py-2">{eventLabel(entry.event_type)}</td><td
										class="max-w-60 truncate px-3 py-2"
										title={sourceLabel(entry)}>{sourceLabel(entry)}</td
									><td class="px-3 py-2 tabular-nums"
										>{formatSignedChatpoint(entry.plan_delta_micros)}</td
									><td class="px-3 py-2 tabular-nums"
										>{formatSignedChatpoint(entry.check_delta_micros)}</td
									><td class="px-3 py-2 tabular-nums"
										>{formatChatpoint(entry.plan_balance_after_micros)}</td
									><td class="px-3 py-2 tabular-nums"
										>{formatChatpoint(entry.check_balance_after_micros)}</td
									></tr
								>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div
					class="rounded-lg border border-gray-100/70 px-3 py-6 text-center text-xs text-gray-500 dark:border-white/[0.08]"
				>
					暂无余额流水
				</div>
			{/if}
			<div class="mt-3 flex items-center justify-end gap-2 text-[11px]">
				<span class="mr-1 text-gray-500"
					>第 {balancePage} / {balancePages} 页 · {formatNumber(ledgerTotal)} 条</span
				><button
					type="button"
					class="page-button"
					aria-label="余额流水上一页"
					title="上一页"
					disabled={balancePage <= 1}
					on:click={() => changeBalancePage(balancePage - 1)}
					><ChevronLeft className="size-3.5" strokeWidth="2" /></button
				><button
					type="button"
					class="page-button"
					aria-label="余额流水下一页"
					title="下一页"
					disabled={balancePage >= balancePages}
					on:click={() => changeBalancePage(balancePage + 1)}
					><ChevronRight className="size-3.5" strokeWidth="2" /></button
				>
			</div>
		{/if}
	</section>
</div>

<style>
	.usage-ledger {
		letter-spacing: 0;
	}

	.status-badge {
		display: inline-flex;
		align-items: center;
		border-radius: 0.375rem;
		background: rgb(243 244 246);
		padding: 0.2rem 0.45rem;
		color: rgb(75 85 99);
		white-space: nowrap;
	}

	.status-green {
		background: rgb(236 253 245);
		color: rgb(4 120 87);
	}

	.status-amber {
		background: rgb(255 251 235);
		color: rgb(180 83 9);
	}

	.page-button {
		display: inline-flex;
		height: 1.75rem;
		width: 1.75rem;
		align-items: center;
		justify-content: center;
		border: 1px solid rgb(243 244 246);
		border-radius: 0.5rem;
	}

	.page-button:hover:not(:disabled) {
		background: rgb(249 250 251);
	}

	.page-button:disabled {
		opacity: 0.4;
	}

	:global(.dark) .status-badge {
		background: rgb(255 255 255 / 0.06);
		color: rgb(209 213 219);
	}

	:global(.dark) .status-green {
		background: rgb(6 78 59 / 0.35);
		color: rgb(110 231 183);
	}

	:global(.dark) .status-amber {
		background: rgb(120 53 15 / 0.35);
		color: rgb(252 211 77);
	}

	:global(.dark) .page-button {
		border-color: rgb(255 255 255 / 0.08);
	}

	:global(.dark) .page-button:hover:not(:disabled) {
		background: rgb(255 255 255 / 0.05);
	}
</style>
