<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as I18n } from 'i18next';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import {
		getAssets,
		shareAsset,
		revokeAssetShare,
		deleteAsset,
		type Asset
	} from '$lib/apis/assets';
	import { WEBUI_NAME, showSidebar } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Download from '$lib/components/icons/Download.svelte';
	import Share from '$lib/components/icons/Share.svelte';
	import Trash from '$lib/components/icons/Trash.svelte';
	import LinkSlash from '$lib/components/icons/LinkSlash.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import FilePlusAlt from '$lib/components/icons/FilePlusAlt.svelte';

	const i18n = getContext<Writable<I18n>>('i18n');

	let assets: Asset[] = [];
	let total = 0;
	let loading = true;
	let activeSource = '';
	let activeCategory = '';
	let query = '';
	let sharingId: string | null = null;
	let deletingId: string | null = null;
	let revokingShareId: string | null = null;

	const absoluteAssetUrl = (path: string) =>
		path.startsWith('http') ? path : `${WEBUI_API_BASE_URL.replace('/api/v1', '')}${path}`;

	const loadAssets = async () => {
		loading = true;
		try {
			const result = await getAssets(localStorage.token, {
				source: activeSource,
				category: activeCategory,
				query: query.trim()
			});
			assets = result.items;
			total = result.total;
		} catch (error) {
			toast.error(`${error}`);
			assets = [];
			total = 0;
		} finally {
			loading = false;
		}
	};

	const formatSize = (size?: number | null) => {
		if (!size) return '';
		if (size < 1024) return `${size} B`;
		if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
		return `${(size / (1024 * 1024)).toFixed(1)} MB`;
	};

	const iconLabel = (asset: Asset) => {
		if (asset.category === 'image') return $i18n.t('Image');
		if (asset.category === 'video') return $i18n.t('Video');
		return $i18n.t('File');
	};

	const copyShareLink = async (asset: Asset) => {
		sharingId = asset.id;
		try {
			const result = await shareAsset(localStorage.token, asset.id);
			await navigator.clipboard.writeText(result.url);
			assets = assets.map((item) =>
				item.id === asset.id
					? {
							...item,
							active_shares: [
								...item.active_shares,
								{
									id: result.id,
									created_at: Math.floor(Date.now() / 1000),
									expires_at: result.expires_at
								}
							]
						}
					: item
			);
			toast.success($i18n.t('Share link copied'));
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			sharingId = null;
		}
	};

	const removeAsset = async (asset: Asset) => {
		if (!confirm($i18n.t('Delete this asset?'))) return;
		deletingId = asset.id;
		try {
			await deleteAsset(localStorage.token, asset.id);
			assets = assets.filter((item) => item.id !== asset.id);
			total = Math.max(0, total - 1);
			toast.success($i18n.t('Asset deleted'));
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			deletingId = null;
		}
	};

	const revokeShare = async (shareId: string) => {
		revokingShareId = shareId;
		try {
			await revokeAssetShare(localStorage.token, shareId);
			assets = assets.map((asset) => ({
				...asset,
				active_shares: asset.active_shares.filter((share) => share.id !== shareId)
			}));
			toast.success($i18n.t('Share revoked'));
		} catch (error) {
			toast.error(`${error}`);
		} finally {
			revokingShareId = null;
		}
	};

	onMount(loadAssets);
</script>

<svelte:head>
	<title>{$i18n.t('Asset Center')} / {$WEBUI_NAME}</title>
</svelte:head>

<div
	class="flex min-w-0 flex-1 flex-col h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: 'md:max-w-[calc(100%-42px)]'} max-w-full"
>
	<div class="flex-1 overflow-y-auto">
		<div class="mx-auto w-full max-w-6xl px-4 pb-12 pt-8 sm:px-8 lg:px-12">
			<div class="flex flex-wrap items-end justify-between gap-4">
				<div>
					<div
						class="mb-1 flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-gray-600"
					>
						<ArchiveBox className="size-3.5" strokeWidth="1.5" />
						<span>{$i18n.t('Library')}</span>
					</div>
					<h1 class="text-2xl font-medium tracking-tight text-gray-900 dark:text-gray-100">
						{$i18n.t('Asset Center')}
					</h1>
					<p class="mt-1 text-sm text-gray-500 dark:text-gray-500">
						{$i18n.t('Your uploads and generated files in one place')}
					</p>
				</div>
				<div class="text-xs text-gray-400 dark:text-gray-600">{total} {$i18n.t('assets')}</div>
			</div>

			<div
				class="mt-8 flex flex-col gap-3 border-b border-gray-100 pb-3 dark:border-gray-800/60 sm:flex-row sm:items-center sm:justify-between"
			>
				<div class="flex flex-wrap items-center gap-1">
					{#each [{ key: '', label: $i18n.t('All') }, { key: 'uploaded', label: $i18n.t('Uploaded') }, { key: 'generated', label: $i18n.t('Generated') }] as tab}
						<button
							type="button"
							class="rounded-lg px-3 py-1.5 text-xs transition {activeSource === tab.key
								? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900'
								: 'text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'}"
							on:click={() => {
								activeSource = tab.key;
								loadAssets();
							}}
						>
							{tab.label}
						</button>
					{/each}
				</div>
				<div class="flex min-w-0 items-center gap-2">
					<input
						class="min-w-0 w-full rounded-lg border border-gray-100 bg-transparent px-3 py-1.5 text-xs outline-none placeholder:text-gray-400 focus:border-gray-300 dark:border-gray-800 dark:focus:border-gray-600 sm:w-56"
						placeholder={$i18n.t('Search assets')}
						bind:value={query}
						on:keydown={(event) => event.key === 'Enter' && loadAssets()}
					/>
				</div>
			</div>

			<div class="mt-4 flex flex-wrap gap-1">
				{#each [{ key: '', label: $i18n.t('All types') }, { key: 'image', label: $i18n.t('Images') }, { key: 'video', label: $i18n.t('Videos') }, { key: 'other', label: $i18n.t('Other files') }] as tab}
					<button
						type="button"
						class="rounded-full border px-2.5 py-1 text-[11px] transition {activeCategory ===
						tab.key
							? 'border-gray-900 text-gray-900 dark:border-white dark:text-white'
							: 'border-gray-100 text-gray-500 hover:border-gray-300 dark:border-gray-800 dark:text-gray-500 dark:hover:border-gray-600'}"
						on:click={() => {
							activeCategory = tab.key;
							loadAssets();
						}}
					>
						{tab.label}
					</button>
				{/each}
			</div>

			{#if loading}
				<div class="flex min-h-64 items-center justify-center"><Spinner className="size-5" /></div>
			{:else if assets.length === 0}
				<div class="flex min-h-64 flex-col items-center justify-center text-center">
					<FilePlusAlt className="size-8 text-gray-300 dark:text-gray-700" strokeWidth="1.2" />
					<div class="mt-3 text-sm text-gray-500 dark:text-gray-500">
						{$i18n.t('No assets yet')}
					</div>
					<div class="mt-1 text-xs text-gray-400 dark:text-gray-600">
						{$i18n.t('Uploaded and generated files will appear here')}
					</div>
				</div>
			{:else}
				<div class="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
					{#each assets as asset (asset.id)}
						<article
							class="group overflow-hidden rounded-xl border border-gray-100 bg-white/60 dark:border-gray-800/70 dark:bg-gray-900/30"
						>
							<div
								class="relative flex aspect-[4/3] items-center justify-center overflow-hidden bg-gray-50 dark:bg-gray-950/60"
							>
								{#if asset.category === 'image'}
									<img
										src={absoluteAssetUrl(asset.preview_url)}
										alt={asset.filename}
										class="size-full object-cover"
										loading="lazy"
									/>
								{:else if asset.category === 'video'}
									<!-- svelte-ignore a11y-media-has-caption -->
									<video
										src={absoluteAssetUrl(asset.preview_url)}
										controls
										preload="metadata"
										class="size-full object-contain"
									></video>
								{:else}
									<ArchiveBox
										className="size-10 text-gray-300 dark:text-gray-700"
										strokeWidth="1.2"
									/>
								{/if}
								<div
									class="pointer-events-none absolute left-2 top-2 rounded-md bg-black/55 px-2 py-1 text-[10px] text-white backdrop-blur-sm"
								>
									{iconLabel(asset)}
								</div>
							</div>
							<div class="p-3">
								<div
									class="truncate text-sm text-gray-800 dark:text-gray-200"
									title={asset.filename}
								>
									{asset.filename}
								</div>
								<div
									class="mt-1 flex items-center justify-between gap-2 text-[11px] text-gray-400 dark:text-gray-600"
								>
									<span
										>{asset.source === 'generated'
											? $i18n.t('Generated')
											: $i18n.t('Uploaded')}</span
									>
									<span>{formatSize(asset.size)}</span>
								</div>
								<div
									class="mt-3 flex items-center justify-end gap-1 border-t border-gray-100 pt-2 dark:border-gray-800/70"
								>
									{#if asset.active_shares.length > 0}
										{#each asset.active_shares as share}
											<Tooltip content={$i18n.t('Revoke share')}>
												<button
													class="flex size-7 items-center justify-center rounded-lg text-amber-600 hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-950/30"
													type="button"
													on:click={() => revokeShare(share.id)}
													aria-label={$i18n.t('Revoke share')}
													disabled={revokingShareId === share.id}
												>
													{#if revokingShareId === share.id}<Spinner
															className="size-3.5"
														/>{:else}<LinkSlash className="size-3.5" strokeWidth="1.6" />{/if}
												</button>
											</Tooltip>
										{/each}
									{/if}
									<Tooltip content={$i18n.t('Download')}>
										<a
											class="flex size-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-800 dark:hover:bg-gray-800 dark:hover:text-gray-200"
											href={absoluteAssetUrl(asset.download_url)}
											aria-label={$i18n.t('Download')}
										>
											<Download className="size-3.5" strokeWidth="1.6" />
										</a>
									</Tooltip>
									<Tooltip content={$i18n.t('Share')}>
										<button
											class="flex size-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-800 dark:hover:bg-gray-800 dark:hover:text-gray-200"
											type="button"
											on:click={() => copyShareLink(asset)}
											aria-label={$i18n.t('Share')}
											disabled={sharingId === asset.id}
										>
											{#if sharingId === asset.id}<Spinner className="size-3.5" />{:else}<Share
													className="size-3.5"
													strokeWidth="1.6"
												/>{/if}
										</button>
									</Tooltip>
									<Tooltip content={$i18n.t('Delete')}>
										<button
											class="flex size-7 items-center justify-center rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30 dark:hover:text-red-400"
											type="button"
											on:click={() => removeAsset(asset)}
											aria-label={$i18n.t('Delete')}
											disabled={deletingId === asset.id}
										>
											{#if deletingId === asset.id}<Spinner className="size-3.5" />{:else}<Trash
													className="size-3.5"
													strokeWidth="1.6"
												/>{/if}
										</button>
									</Tooltip>
								</div>
							</div>
						</article>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>
