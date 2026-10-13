<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		ArrowUpRight,
		Check,
		CircleCheck,
		KeyRound,
		Plus,
		RefreshCw,
		ShieldCheck,
		Sparkles,
		Trash2,
		Zap
	} from '@lucide/svelte';
	import { getBackendConfig, getModels as getAllModels } from '$lib/apis';
	import { getOpenAIConfig, updateOpenAIConfig, verifyOpenAIConnection } from '$lib/apis/openai';
	import {
		config as configStore,
		models as modelsStore,
		settings as settingsStore
	} from '$lib/stores';
	import ThemeLogo from '$lib/components/common/ThemeLogo.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import {
		ARTIAPI_BASE_URL,
		getArtiAPIKeys,
		mergeArtiAPIKeys,
		type ArtiAPIKeyConfig,
		type OpenAIProviderConfig
	} from './artiAPIConnections';

	export let embedded = false;
	export let compact = false;
	const dispatch = createEventDispatcher<{ saved: OpenAIProviderConfig }>();

	type ArtiModel = { id: string; label: string; group: string };
	type KeyDraft = {
		id: number;
		originalKey?: string;
		apiKey: string;
		enabled: boolean;
		showKey: boolean;
		availableModels: ArtiModel[];
		selectedModels: Set<string>;
		selectionExplicit: boolean;
		verifiedKey: string | null;
		refreshing: boolean;
		requestId: number;
	};

	let nextId = 0;
	let drafts: KeyDraft[] = [];
	let loading = true;
	let loadFailed = false;
	let saving = false;
	let saved = false;
	$: enabled = drafts.some((entry) => entry.enabled);
	$: refreshing = drafts.some((entry) => entry.refreshing);

	const createDraft = (stored?: ArtiAPIKeyConfig): KeyDraft => {
		const modelIds: string[] = Array.isArray(stored?.config.model_ids)
			? stored.config.model_ids
			: [];
		return {
			id: ++nextId,
			originalKey: stored?.key,
			apiKey: stored?.key ?? '',
			enabled: stored ? stored.config.enable !== false : false,
			showKey: false,
			availableModels: modelIds.map((id) => ({ id, label: id, group: 'ArtiAPI' })),
			selectedModels: new Set(modelIds),
			selectionExplicit: modelIds.length > 0,
			verifiedKey: null,
			refreshing: false,
			requestId: 0
		};
	};

	const patchDraft = (id: number, changes: Partial<KeyDraft>) => {
		drafts = drafts.map((entry) => (entry.id === id ? { ...entry, ...changes } : entry));
		saved = false;
	};
	const addKey = () => {
		drafts = [...drafts, { ...createDraft(), enabled: true }];
		saved = false;
	};
	const removeKey = (id: number) => {
		drafts = drafts.filter((entry) => entry.id !== id);
		saved = false;
	};
	const setKey = (entry: KeyDraft, value: string) => {
		patchDraft(entry.id, {
			apiKey: value,
			...(value.trim() !== entry.apiKey.trim()
				? {
						availableModels: [],
						selectedModels: new Set<string>(),
						selectionExplicit: false,
						verifiedKey: null,
						refreshing: false,
						requestId: entry.requestId + 1
					}
				: {})
		});
	};
	const setEnabled = (value: boolean) => {
		drafts = drafts.length
			? drafts.map((entry) => ({ ...entry, enabled: value }))
			: [{ ...createDraft(), enabled: value }];
		saved = false;
	};
	const toggleModel = (entry: KeyDraft, modelId: string) => {
		const selectedModels = new Set(entry.selectedModels);
		if (selectedModels.has(modelId)) selectedModels.delete(modelId);
		else selectedModels.add(modelId);
		patchDraft(entry.id, { selectedModels, selectionExplicit: true });
	};

	const parseModels = (response: any): ArtiModel[] => {
		const data = Array.isArray(response) ? response : response?.data;
		if (!Array.isArray(data)) return [];
		const seen = new Set<string>();
		return data.flatMap((model) => {
			const id = String(model?.id ?? model?.name ?? '').trim();
			if (!id || seen.has(id)) return [];
			seen.add(id);
			return [
				{
					id,
					label: String(model?.name ?? id),
					group: String(model?.owned_by ?? model?.provider ?? 'ArtiAPI')
				}
			];
		});
	};

	const refreshModels = async (id: number) => {
		const entry = drafts.find((entry) => entry.id === id);
		const key = entry?.apiKey.trim();
		if (!entry || !key) {
			toast.error('请先输入 ArtiAPI 密钥');
			return false;
		}
		const requestId = entry.requestId + 1;
		patchDraft(id, { refreshing: true, verifiedKey: null, requestId });
		try {
			const response = await verifyOpenAIConnection(localStorage.token, {
				url: ARTIAPI_BASE_URL,
				key,
				config: { enable: true }
			});
			const current = drafts.find((entry) => entry.id === id);
			if (!current || current.requestId !== requestId || current.apiKey.trim() !== key)
				return false;
			const availableModels = parseModels(response);
			const selectedModels = new Set(
				availableModels
					.filter((model) => !current.selectionExplicit || current.selectedModels.has(model.id))
					.map((model) => model.id)
			);
			patchDraft(id, { availableModels, selectedModels, verifiedKey: key });
			return true;
		} catch (error) {
			const current = drafts.find((entry) => entry.id === id);
			if (current?.requestId === requestId) toast.error(`${error}`);
			return false;
		} finally {
			if (drafts.find((entry) => entry.id === id)?.requestId === requestId)
				patchDraft(id, { refreshing: false });
		}
	};

	const loadConfig = async () => {
		loading = true;
		loadFailed = false;
		try {
			const current = await getOpenAIConfig(localStorage.token);
			if (!current) throw '无法读取连接配置';
			const stored = getArtiAPIKeys(current);
			drafts = stored.length ? stored.map(createDraft) : [createDraft()];
		} catch (error) {
			loadFailed = true;
			toast.error(`${error}`);
		} finally {
			loading = false;
		}
	};

	const saveConfig = async () => {
		if (drafts.some((entry) => entry.enabled && !entry.apiKey.trim())) {
			toast.error('请为已启用的连接填写密钥');
			return;
		}
		const keys = drafts.filter((entry) => entry.apiKey.trim()).map((entry) => entry.apiKey.trim());
		if (new Set(keys).size !== keys.length) {
			toast.error('密钥重复，请为每个连接填写不同的密钥');
			return;
		}
		saving = true;
		try {
			for (const entry of drafts.filter((entry) => entry.enabled)) {
				if (entry.verifiedKey !== entry.apiKey.trim() && !(await refreshModels(entry.id))) return;
			}
			if (drafts.some((entry) => entry.enabled && entry.selectedModels.size === 0)) {
				toast.error('请为每个已启用的密钥选择至少一个可用模型');
				return;
			}
			const current = await getOpenAIConfig(localStorage.token);
			if (!current) throw '无法读取连接配置';
			const next = mergeArtiAPIKeys(
				current,
				drafts
					.filter((entry) => entry.apiKey.trim())
					.map((entry) => ({
						key: entry.apiKey,
						originalKey: entry.originalKey,
						config: { enable: entry.enabled, model_ids: [...entry.selectedModels] }
					}))
			);
			const response = await updateOpenAIConfig(localStorage.token, next);
			if (!response) throw 'ArtiAPI 配置保存失败';
			drafts = drafts
				.filter((entry) => entry.apiKey.trim())
				.map((entry) => ({
					...entry,
					apiKey: entry.apiKey.trim(),
					originalKey: entry.apiKey.trim()
				}));
			dispatch('saved', response);
			await configStore.set(await getBackendConfig());
			try {
				await modelsStore.set(
					await getAllModels(
						localStorage.token,
						$configStore?.features?.enable_direct_connections
							? ($settingsStore?.directConnections ?? null)
							: null,
						false,
						true
					)
				);
			} catch {
				// Saving the connection does not depend on refreshing the global model cache.
			}
			saved = true;
			toast.success('ArtiAPI 配置已保存');
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			saving = false;
		}
	};

	onMount(loadConfig);
</script>

<div
	class={embedded
		? ''
		: 'min-h-screen bg-[#f7f7f8] px-4 py-8 text-[#242424] dark:bg-[#111214] dark:text-[#f4f4f5] sm:px-8'}
>
	<div class={embedded ? 'w-full' : 'mx-auto max-w-3xl'}>
		<section
			class={`overflow-hidden ${compact ? 'rounded-xl' : 'rounded-2xl'} border border-gray-200/80 bg-white dark:border-white/[0.08] dark:bg-[#1a1b1f]`}
		>
			<div
				class={`border-b border-gray-100 dark:border-white/[0.06] ${compact ? 'px-4 py-4 sm:px-5' : 'px-5 py-5 sm:px-7 sm:py-6'}`}
			>
				<div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
					<div class="flex min-w-0 gap-3">
						<div class="flex size-10 shrink-0 items-center justify-center">
							<ThemeLogo kind="mark" className="size-10 object-contain" alt="ArtiChat LOGO" />
						</div>
						<div class="min-w-0">
							<div class="mb-1 flex flex-wrap items-center gap-2">
								<h3 class="text-base font-semibold tracking-[-0.01em]">ArtiAPI</h3>
								<span
									class="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[0.625rem] font-medium text-emerald-700 dark:bg-emerald-400/10 dark:text-emerald-300"
									><Sparkles size={11} strokeWidth={2} />推荐接入</span
								>
							</div>
							<p class="text-sm leading-6 text-gray-500 dark:text-gray-400">
								您可以选择使用我们的ArtiAPI作为模型提供商，一键式使用多款模型。
							</p>
						</div>
					</div>
					<a
						class="inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-gray-200 px-3 text-xs font-medium text-gray-700 transition hover:border-gray-300 hover:bg-gray-50 dark:border-white/[0.1] dark:text-gray-200 dark:hover:bg-white/[0.06]"
						href="https://api.artivis.cc"
						target="_blank"
						rel="noreferrer">前往官网 <ArrowUpRight size={14} strokeWidth={1.8} /></a
					>
				</div>
			</div>

			<div class={compact ? 'px-4 py-4 sm:px-5' : 'px-5 py-5 sm:px-7 sm:py-6'}>
				{#if loading}
					<div class="flex min-h-24 items-center justify-center text-xs text-gray-400">
						正在读取 ArtiAPI 配置…
					</div>
				{:else if loadFailed}
					<button type="button" class="text-xs text-gray-500 underline" on:click={loadConfig}
						>配置加载失败，点击重试</button
					>
				{:else}
					<div class="flex items-center justify-between gap-4">
						<div class="flex min-w-0 items-center gap-2.5">
							<Zap size={16} class="shrink-0 text-gray-500 dark:text-gray-400" />
							<div class="text-sm font-medium">启用 ArtiAPI</div>
						</div>
						<Switch
							state={enabled}
							ariaLabel="启用 ArtiAPI"
							disabled={saving}
							on:change={(event) => setEnabled(event.detail)}
						/>
					</div>
					<p
						class="mt-2 flex items-start gap-1.5 text-[0.6875rem] leading-5 text-gray-400 dark:text-gray-500"
					>
						<ShieldCheck
							size={13}
							class="mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400"
							strokeWidth={1.8}
						/><span>一键直接连接到ArtiAPI，无需其他配置</span>
					</p>

					<div class="mb-2 mt-4 flex items-center justify-between gap-3">
						<div class="text-xs font-medium text-gray-600 dark:text-gray-300">
							API 密钥 <span class="ml-1 font-normal text-gray-400">{drafts.length}</span>
						</div>
						<button
							type="button"
							class="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs text-gray-600 transition hover:bg-gray-100 disabled:opacity-50 dark:text-gray-300 dark:hover:bg-white/[0.06]"
							disabled={saving}
							on:click={addKey}><Plus size={13} />新增密钥</button
						>
					</div>
					<div class="space-y-3">
						{#each drafts as entry, index (entry.id)}
							<div class="rounded-lg border border-gray-200/80 p-3 dark:border-white/[0.08]">
								<div class="mb-2 flex items-center justify-between gap-3">
									<label
										class="flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-300"
										for={`artiapi-key-${entry.id}`}><KeyRound size={13} />密钥 {index + 1}</label
									>
									<div class="flex items-center gap-3">
										<Switch
											state={entry.enabled}
											ariaLabel={`启用密钥 ${index + 1}`}
											disabled={saving}
											on:change={(event) => patchDraft(entry.id, { enabled: event.detail })}
										/>
										<button
											type="button"
											class="rounded p-1 text-gray-400 transition hover:bg-red-50 hover:text-red-500 disabled:opacity-50 dark:hover:bg-red-500/10"
											aria-label={`删除密钥 ${index + 1}`}
											title="删除密钥"
											disabled={saving}
											on:click={() => removeKey(entry.id)}><Trash2 size={14} /></button
										>
									</div>
								</div>
								<div
									class="flex h-9 items-center gap-2 rounded-lg border border-gray-200 bg-gray-50/70 px-3 focus-within:border-gray-400 dark:border-white/[0.1] dark:bg-white/[0.025] dark:focus-within:border-white/[0.25]"
								>
									<input
										id={`artiapi-key-${entry.id}`}
										class="min-w-0 flex-1 bg-transparent text-sm text-gray-800 outline-hidden placeholder:text-gray-300 disabled:opacity-60 dark:text-gray-200 dark:placeholder:text-gray-600"
										type={entry.showKey ? 'text' : 'password'}
										value={entry.apiKey}
										on:input={(event) => setKey(entry, event.currentTarget.value)}
										disabled={saving}
										autocomplete="new-password"
										placeholder="输入 ArtiAPI 密钥"
									/>
									<button
										type="button"
										class="shrink-0 text-[0.6875rem] text-gray-400 transition hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-200"
										on:click={() => patchDraft(entry.id, { showKey: !entry.showKey })}
										>{entry.showKey ? '隐藏' : '显示'}</button
									>
								</div>
								<div class="mb-2 mt-3 flex flex-wrap items-center justify-between gap-2">
									<span class="text-[0.6875rem] text-gray-400 dark:text-gray-500"
										>{entry.selectedModels.size} / {entry.availableModels.length} 个模型已选择</span
									>
									<button
										type="button"
										class="inline-flex h-6 items-center gap-1 rounded-md px-2 text-[0.6875rem] text-gray-500 transition hover:bg-gray-100 disabled:opacity-50 dark:text-gray-400 dark:hover:bg-white/[0.06]"
										disabled={saving || entry.refreshing || !entry.apiKey.trim()}
										on:click={() => refreshModels(entry.id)}
										><RefreshCw
											size={12}
											class={entry.refreshing ? 'animate-spin' : ''}
										/>{entry.refreshing ? '读取中' : '刷新模型'}</button
									>
								</div>
								{#if entry.availableModels.length}
									<div class="grid max-h-48 gap-2 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
										{#each entry.availableModels as model (model.id)}
											<button
												type="button"
												class="flex min-w-0 items-center gap-2 rounded-md border px-2.5 py-2 text-left text-xs transition {entry.selectedModels.has(
													model.id
												)
													? 'border-gray-300 bg-gray-50 text-gray-800 dark:border-white/[0.18] dark:bg-white/[0.06] dark:text-gray-100'
													: 'border-gray-200/60 text-gray-400 dark:border-white/[0.06] dark:text-gray-500'}"
												aria-pressed={entry.selectedModels.has(model.id)}
												disabled={saving || entry.refreshing}
												on:click={() => toggleModel(entry, model.id)}
											>
												<span
													class="flex size-4 shrink-0 items-center justify-center rounded border {entry.selectedModels.has(
														model.id
													)
														? 'border-gray-900 bg-gray-900 text-white dark:border-white dark:bg-white dark:text-gray-900'
														: 'border-gray-300 dark:border-white/[0.2]'}"
													>{#if entry.selectedModels.has(model.id)}<Check size={11} />{/if}</span
												>
												<span class="min-w-0 truncate" title={`${model.group} · ${model.id}`}
													>{model.label}</span
												>
											</button>
										{/each}
									</div>
								{:else}
									<p class="py-2 text-[0.6875rem] text-gray-400 dark:text-gray-500">
										填写密钥后刷新模型，也可直接保存以读取可用模型。
									</p>
								{/if}
								{#if entry.verifiedKey === entry.apiKey.trim()}<p
										class="mt-2 flex items-center gap-1 text-[0.6875rem] text-emerald-600 dark:text-emerald-400"
									>
										<CircleCheck size={12} />密钥连接已验证
									</p>{/if}
							</div>
						{:else}
							<p
								class="rounded-lg border border-dashed border-gray-200 p-4 text-center text-xs text-gray-400 dark:border-white/[0.1]"
							>
								尚未配置密钥，点击“新增密钥”开始使用。
							</p>
						{/each}
					</div>

					<div
						class="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-3 dark:border-white/[0.06]"
					>
						<span class="text-[0.6875rem] text-gray-400 dark:text-gray-500"
							>{saved ? '配置已保存，模型列表已更新' : '每个密钥可独立启用并选择模型'}</span
						>
						<button
							type="button"
							class="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-[#24262b] px-3.5 text-xs font-medium text-white transition hover:bg-[#111216] disabled:opacity-60 dark:bg-white dark:text-[#17181b] dark:hover:bg-gray-100"
							disabled={saving || refreshing}
							on:click={saveConfig}><Check size={14} />{saving ? '保存中…' : '保存配置'}</button
						>
					</div>
				{/if}
			</div>
		</section>
	</div>
</div>
