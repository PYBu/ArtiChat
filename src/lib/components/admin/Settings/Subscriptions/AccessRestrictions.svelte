<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Switch from '$lib/components/common/Switch.svelte';
	import {
		createAccessRestrictionIPRule,
		createAccessRestrictionRegion,
		deleteAccessRestrictionIPRule,
		deleteAccessRestrictionRegion,
		getAccessRestrictionConfig,
		getAccessRestrictionIPRules,
		getAccessRestrictionLoginRecords,
		getAccessRestrictionRegions,
		updateAccessRestrictionConfig,
		updateAccessRestrictionIPRule,
		updateAccessRestrictionRegion,
		type AccessRestrictionConfig,
		type IPRule,
		type LoginEvent,
		type RegionRule
	} from '$lib/apis/access-restrictions';

	let restrictionConfig: AccessRestrictionConfig | null = null;
	let ipRules: IPRule[] = [];
	let regionRules: RegionRule[] = [];
	let loginRecords: LoginEvent[] = [];
	let totalRecords = 0;
	let loading = true;
	let saving = false;
	let query = '';
	let resultFilter = '';
	let recordsPage = 0;
	const pageSize = 50;

	let ipNetwork = '';
	let ipNote = '';
	let countryCode = '';
	let countryNote = '';
	let addingIp = false;
	let addingCountry = false;
	let savingIds = new Set<string>();

	const errorText = (error: unknown) =>
		typeof error === 'string' ? error : error instanceof Error ? error.message : String(error);

	const loadRecords = async () => {
		const result = await getAccessRestrictionLoginRecords(localStorage.token, {
			query: query.trim() || undefined,
			result: resultFilter || undefined,
			limit: pageSize,
			offset: recordsPage * pageSize
		});
		loginRecords = result.items;
		totalRecords = result.total_item_count;
	};

	const load = async () => {
		loading = true;
		try {
			const [nextConfig, nextIps, nextRegions] = await Promise.all([
				getAccessRestrictionConfig(localStorage.token),
				getAccessRestrictionIPRules(localStorage.token),
				getAccessRestrictionRegions(localStorage.token)
			]);
			restrictionConfig = nextConfig;
			ipRules = nextIps.items;
			regionRules = nextRegions.items;
			recordsPage = 0;
			await loadRecords();
		} catch (error) {
			toast.error(errorText(error));
		} finally {
			loading = false;
		}
	};

	const toggleEnabled = async () => {
		if (!restrictionConfig || saving) return;
		const previous = restrictionConfig.enabled;
		restrictionConfig = { ...restrictionConfig, enabled: !previous };
		saving = true;
		try {
			restrictionConfig = await updateAccessRestrictionConfig(
				localStorage.token,
				restrictionConfig.enabled
			);
			toast.success(restrictionConfig.enabled ? '限制策略已启用' : '限制策略已停用');
		} catch (error) {
			restrictionConfig = { ...restrictionConfig, enabled: previous };
			toast.error(errorText(error));
		} finally {
			saving = false;
		}
	};

	const addIpRule = async () => {
		if (!ipNetwork.trim() || addingIp) return;
		addingIp = true;
		try {
			const created = await createAccessRestrictionIPRule(localStorage.token, {
				network: ipNetwork.trim(),
				note: ipNote.trim() || null,
				enabled: true
			});
			ipRules = [created, ...ipRules];
			ipNetwork = '';
			ipNote = '';
			toast.success('IP 规则已添加');
		} catch (error) {
			toast.error(errorText(error));
		} finally {
			addingIp = false;
		}
	};

	const addCountryRule = async () => {
		if (!countryCode.trim() || addingCountry) return;
		addingCountry = true;
		try {
			const created = await createAccessRestrictionRegion(localStorage.token, {
				country_code: countryCode.trim().toUpperCase(),
				note: countryNote.trim() || null,
				enabled: true
			});
			regionRules = [...regionRules, created].sort((a, b) =>
				a.country_code.localeCompare(b.country_code)
			);
			countryCode = '';
			countryNote = '';
			toast.success('国家规则已添加');
		} catch (error) {
			toast.error(errorText(error));
		} finally {
			addingCountry = false;
		}
	};

	const toggleIpRule = async (row: IPRule) => {
		if (savingIds.has(row.id)) return;
		const previous = row.enabled;
		row.enabled = !previous;
		ipRules = [...ipRules];
		savingIds = new Set([...savingIds, row.id]);
		try {
			const updated = await updateAccessRestrictionIPRule(localStorage.token, row.id, {
				enabled: row.enabled
			});
			Object.assign(row, updated);
		} catch (error) {
			row.enabled = previous;
			toast.error(errorText(error));
		} finally {
			ipRules = [...ipRules];
			const next = new Set(savingIds);
			next.delete(row.id);
			savingIds = next;
		}
	};

	const toggleCountryRule = async (row: RegionRule) => {
		if (savingIds.has(row.id)) return;
		const previous = row.enabled;
		row.enabled = !previous;
		regionRules = [...regionRules];
		savingIds = new Set([...savingIds, row.id]);
		try {
			const updated = await updateAccessRestrictionRegion(localStorage.token, row.id, {
				enabled: row.enabled
			});
			Object.assign(row, updated);
		} catch (error) {
			row.enabled = previous;
			toast.error(errorText(error));
		} finally {
			regionRules = [...regionRules];
			const next = new Set(savingIds);
			next.delete(row.id);
			savingIds = next;
		}
	};

	const removeIpRule = async (row: IPRule) => {
		if (!window.confirm(`删除 IP 规则 ${row.network}？`)) return;
		try {
			await deleteAccessRestrictionIPRule(localStorage.token, row.id);
			ipRules = ipRules.filter((item) => item.id !== row.id);
		} catch (error) {
			toast.error(errorText(error));
		}
	};

	const removeCountryRule = async (row: RegionRule) => {
		if (!window.confirm(`删除国家规则 ${row.country_code}？`)) return;
		try {
			await deleteAccessRestrictionRegion(localStorage.token, row.id);
			regionRules = regionRules.filter((item) => item.id !== row.id);
		} catch (error) {
			toast.error(errorText(error));
		}
	};

	const searchRecords = async () => {
		recordsPage = 0;
		try {
			await loadRecords();
		} catch (error) {
			toast.error(errorText(error));
		}
	};

	const changeRecordsPage = async (delta: number) => {
		const nextPage = recordsPage + delta;
		if (nextPage < 0 || nextPage * pageSize >= totalRecords) return;
		recordsPage = nextPage;
		await searchRecords();
	};

	const formatDate = (timestamp: number) => new Date(timestamp * 1000).toLocaleString();
	const resultLabel = (result: string) =>
		result === 'blocked_ip' ? 'IP 已拒绝' : result === 'blocked_region' ? '地区已拒绝' : '登录成功';
	const resultClass = (result: string) =>
		result === 'success' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';

	onMount(load);
</script>

<div class="admin-operations flex flex-col gap-4">
	<div class="flex flex-wrap items-center justify-between gap-3">
		<div>
			<div class="text-base font-medium">限制管理</div>
			<div class="mt-0.5 text-xs text-gray-500">
				只检查新登录和注册，管理员不受限制。登录记录保留 7 天。
			</div>
		</div>
		{#if restrictionConfig}
			<div class="flex items-center gap-2 text-xs text-gray-500">
				<span>{restrictionConfig.enabled ? '策略已启用' : '策略已停用'}</span>
				<Switch
					bind:state={restrictionConfig.enabled}
					on:change={toggleEnabled}
					ariaLabel="启用登录限制"
				/>
			</div>
		{/if}
	</div>

	{#if loading}
		<div
			class="h-32 animate-pulse rounded-lg border border-gray-100 bg-gray-50 dark:border-gray-850 dark:bg-gray-900"
		></div>
	{:else}
		{#if restrictionConfig && !restrictionConfig.geoip.available}
			<div
				class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-200"
			>
				国家限制暂不可用：尚未找到本地 GeoIP 国家数据库。IP
				黑名单仍然有效，请配置数据库后再启用国家规则。
			</div>
		{/if}
		{#if restrictionConfig?.geoip.provider === 'db-ip-lite'}
			<a
				href="https://db-ip.com"
				target="_blank"
				rel="noreferrer"
				class="self-start text-[11px] text-gray-500 underline underline-offset-2 hover:text-gray-700 dark:hover:text-gray-300"
				>IP Geolocation by DB-IP</a
			>
		{/if}

		<div class="grid gap-3 lg:grid-cols-2">
			<section
				class="rounded-lg border border-gray-100/60 bg-white/40 p-3 dark:border-white/[0.06] dark:bg-white/[0.02]"
			>
				<div class="mb-3 flex items-center justify-between gap-2">
					<div>
						<div class="text-sm font-medium">IP 黑名单</div>
						<div class="text-[11px] text-gray-500">支持单个 IP 或 CIDR 网段。</div>
					</div>
					<span class="text-[11px] text-gray-500">{ipRules.length} 条</span>
				</div>
				<form
					class="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
					on:submit|preventDefault={addIpRule}
				>
					<input
						bind:value={ipNetwork}
						required
						placeholder="例如 203.0.113.10/32"
						class="h-8 min-w-0 rounded-lg border border-gray-100/60 bg-transparent px-2 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.06]"
					/>
					<input
						bind:value={ipNote}
						placeholder="备注（可选）"
						class="h-8 min-w-0 rounded-lg border border-gray-100/60 bg-transparent px-2 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.06]"
					/>
					<button
						disabled={addingIp}
						class="h-8 rounded-lg bg-black px-3 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
						>添加</button
					>
				</form>
				<div class="mt-3 divide-y divide-gray-100 dark:divide-gray-850">
					{#each ipRules as row (row.id)}
						<div class="flex items-center gap-2 py-2 text-xs">
							<div class="min-w-0 flex-1">
								<div class="font-mono text-gray-800 dark:text-gray-200">{row.network}</div>
								{#if row.note}<div class="truncate text-[11px] text-gray-500">{row.note}</div>{/if}
							</div>
							<Switch
								state={row.enabled}
								on:change={() => toggleIpRule(row)}
								ariaLabel={`启用 ${row.network}`}
							/>
							<button
								type="button"
								class="text-gray-400 hover:text-red-600"
								title="删除"
								aria-label="删除 IP 规则"
								on:click={() => removeIpRule(row)}>删除</button
							>
						</div>
					{:else}
						<div class="py-4 text-center text-xs text-gray-500">暂无 IP 黑名单</div>
					{/each}
				</div>
			</section>

			<section
				class="rounded-lg border border-gray-100/60 bg-white/40 p-3 dark:border-white/[0.06] dark:bg-white/[0.02]"
			>
				<div class="mb-3 flex items-center justify-between gap-2">
					<div>
						<div class="text-sm font-medium">国家限制</div>
						<div class="text-[11px] text-gray-500">
							按 IP 解析出的国家代码（ISO 3166-1 alpha-2）。
						</div>
					</div>
					<span class="text-[11px] text-gray-500">{regionRules.length} 条</span>
				</div>
				<form
					class="grid gap-2 sm:grid-cols-[7rem_minmax(0,1fr)_auto]"
					on:submit|preventDefault={addCountryRule}
				>
					<input
						bind:value={countryCode}
						required
						maxlength="2"
						placeholder="例如 CN"
						class="h-8 min-w-0 rounded-lg border border-gray-100/60 bg-transparent px-2 text-xs uppercase outline-hidden focus:border-blue-400 dark:border-white/[0.06]"
					/>
					<input
						bind:value={countryNote}
						placeholder="备注（可选）"
						class="h-8 min-w-0 rounded-lg border border-gray-100/60 bg-transparent px-2 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.06]"
					/>
					<button
						disabled={addingCountry}
						class="h-8 rounded-lg bg-black px-3 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
						>添加</button
					>
				</form>
				<div class="mt-3 divide-y divide-gray-100 dark:divide-gray-850">
					{#each regionRules as row (row.id)}
						<div class="flex items-center gap-2 py-2 text-xs">
							<div class="min-w-0 flex-1">
								<span class="font-mono text-gray-800 dark:text-gray-200">{row.country_code}</span
								>{#if row.note}<span class="ml-2 text-[11px] text-gray-500">{row.note}</span>{/if}
							</div>
							<Switch
								state={row.enabled}
								on:change={() => toggleCountryRule(row)}
								ariaLabel={`启用 ${row.country_code} 限制`}
							/>
							<button
								type="button"
								class="text-gray-400 hover:text-red-600"
								title="删除"
								aria-label="删除国家规则"
								on:click={() => removeCountryRule(row)}>删除</button
							>
						</div>
					{:else}
						<div class="py-4 text-center text-xs text-gray-500">暂无国家限制</div>
					{/each}
				</div>
			</section>
		</div>

		<section
			class="rounded-lg border border-gray-100/60 bg-white/40 p-3 dark:border-white/[0.06] dark:bg-white/[0.02]"
		>
			<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
				<div>
					<div class="text-sm font-medium">近期登录记录</div>
					<div class="text-[11px] text-gray-500">仅保留最近 7 天，包含被拒绝的请求。</div>
				</div>
				<div class="text-[11px] text-gray-500">共 {totalRecords} 条</div>
			</div>
			<form class="flex flex-wrap gap-2" on:submit|preventDefault={searchRecords}>
				<input
					bind:value={query}
					placeholder="搜索用户名或邮箱"
					class="h-8 min-w-52 flex-1 rounded-lg border border-gray-100/60 bg-transparent px-2 text-xs outline-hidden focus:border-blue-400 dark:border-white/[0.06]"
				/>
				<select
					bind:value={resultFilter}
					class="h-8 rounded-lg border border-gray-100/60 bg-transparent px-2 text-xs outline-hidden dark:border-white/[0.06]"
					><option value="">全部结果</option><option value="success">登录成功</option><option
						value="blocked_ip">IP 已拒绝</option
					><option value="blocked_region">地区已拒绝</option></select
				>
				<button
					class="h-8 rounded-lg border border-gray-200 px-3 text-xs font-medium hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-850"
					>搜索</button
				>
			</form>
			<div class="mt-3 overflow-x-auto">
				<table class="w-full min-w-[44rem] text-left text-xs">
					<thead class="text-[11px] text-gray-500"
						><tr
							><th class="pb-2 font-medium">时间</th><th class="pb-2 font-medium">用户</th><th
								class="pb-2 font-medium">登录 IP</th
							><th class="pb-2 font-medium">国家</th><th class="pb-2 font-medium">方式</th><th
								class="pb-2 font-medium">结果</th
							></tr
						></thead
					><tbody class="divide-y divide-gray-100 dark:divide-gray-850">
						{#each loginRecords as row (row.id)}<tr
								><td class="whitespace-nowrap py-2 text-gray-500">{formatDate(row.created_at)}</td
								><td class="max-w-48 truncate py-2"
									><div>{row.user_name || '-'}</div>
									<div class="text-[11px] text-gray-500">{row.user_email || '-'}</div></td
								><td class="py-2 font-mono">{row.ip_address || '-'}</td><td class="py-2"
									>{row.country_code || '-'}</td
								><td class="py-2 text-gray-500">{row.auth_method}</td><td
									class={`py-2 font-medium ${resultClass(row.result)}`}
									>{resultLabel(row.result)}</td
								></tr
							>{:else}<tr
								><td colspan="6" class="py-8 text-center text-xs text-gray-500">暂无登录记录</td
								></tr
							>{/each}
					</tbody>
				</table>
			</div>
			<div class="mt-3 flex items-center justify-between text-xs text-gray-500">
				<span>第 {recordsPage + 1} 页</span>
				<div class="flex gap-2">
					<button
						type="button"
						disabled={recordsPage === 0}
						class="rounded-lg border border-gray-200 px-2 py-1 disabled:opacity-40 dark:border-gray-700"
						on:click={() => changeRecordsPage(-1)}>上一页</button
					><button
						type="button"
						disabled={(recordsPage + 1) * pageSize >= totalRecords}
						class="rounded-lg border border-gray-200 px-2 py-1 disabled:opacity-40 dark:border-gray-700"
						on:click={() => changeRecordsPage(1)}>下一页</button
					>
				</div>
			</div>
		</section>
	{/if}
</div>
