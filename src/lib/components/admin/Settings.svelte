<script>
	import { createEventDispatcher, getContext, tick, onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';

	import { config } from '$lib/stores';
	import { getBackendConfig } from '$lib/apis';
	import Database from './Settings/Database.svelte';

	import Authentication from './Settings/Authentication.svelte';
	import General from './Settings/General.svelte';
	import Update from './Settings/Update.svelte';
	import Pipelines from './Settings/Pipelines.svelte';
	import Audio from './Settings/Audio.svelte';
	import Images from './Settings/Images.svelte';
	import Interface from './Settings/Interface.svelte';
	import Models from './Settings/Models.svelte';
	import Connections from './Settings/Connections.svelte';
	import Documents from './Settings/Documents.svelte';
	import WebSearch from './Settings/WebSearch.svelte';

	import Evaluations from './Settings/Evaluations.svelte';
	import Analytics from './Analytics.svelte';
	import CodeExecution from './Settings/CodeExecution.svelte';
	import Integrations from './Settings/Integrations.svelte';
	import Subagents from './Settings/Subagents.svelte';
	import Platform from './Settings/Platform.svelte';
	import Email from './Settings/Email.svelte';

	import Search from '../icons/Search.svelte';
	import ChevronLeft from '../icons/ChevronLeft.svelte';
	import AdminTabIcon from './Settings/AdminTabIcon.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let modal = false;
	export let selectedTab = 'general';
	/** @type {Record<string, unknown> | null} */
	export let tabState = null;

	const validTabs = [
		'platform',
		'general',
		'update',
		'authentication',
		'connections',
		'models',
		'subagents',
		'evaluations',
		'analytics',
		'integrations',
		'documents',
		'web',
		'code-execution',
		'interface',
		'audio',
		'images',
		'pipelines',
		'db',
		'email'
	];

	// Get current tab from URL pathname, default to 'general'
	$: if (!modal) {
		const pathParts = $page.url.pathname.split('/');
		const tabFromPath = pathParts[pathParts.length - 1];
		selectedTab = validTabs.includes(tabFromPath) ? tabFromPath : 'general';
		const modelId = $page.url.searchParams.get('model');
		tabState = selectedTab === 'models' && modelId ? { id: modelId } : null;
	}

	$: if (modal && !validTabs.includes(selectedTab)) selectedTab = 'general';
	$: analyticsEnabled = $config?.features.enable_admin_analytics ?? true;
	$: if (!analyticsEnabled && selectedTab === 'analytics') {
		selectedTab = 'general';
		if (!modal && typeof window !== 'undefined') {
			goto('/admin/settings/general', { replaceState: true });
		}
	}

	$: if (selectedTab) {
		// scroll to selectedTab
		scrollToTab(selectedTab);
	}

	const scrollToTab = (tabId) => {
		const tabElement = document.getElementById(tabId);
		if (tabElement) {
			tabElement.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
		}
	};

	let search = '';
	let searchDebounceTimeout;
	let filteredSettings = [];

	const allSettings = [
		{
			id: 'platform',
			title: 'Platform',
			route: '/admin/settings/platform',
			keywords: ['platform', 'branding', 'name', 'logo', 'about', 'sidebar', 'customization']
		},
		{
			id: 'general',
			title: 'General',
			route: '/admin/settings/general',
			keywords: [
				'general',
				'admin',
				'settings',
				'language',
				'theme',
				'data',
				'users',
				'roles',
				'ldap',
				'authentication',
				'reverse proxy',
				'webhook',
				'community',
				'channels'
			]
		},
		{
			id: 'authentication',
			title: 'Authentication',
			route: '/admin/settings/authentication',
			keywords: [
				'authentication',
				'auth',
				'login',
				'signup',
				'ldap',
				'oauth',
				'oidc',
				'sso',
				'roles',
				'groups',
				'identity'
			]
		},
		{
			id: 'connections',
			title: 'Connections',
			route: '/admin/settings/connections',
			keywords: [
				'connections',
				'ollama',
				'openai',
				'api',
				'base url',
				'direct connections',
				'proxy',
				'key'
			]
		},
		{
			id: 'models',
			title: 'Models',
			route: '/admin/settings/models',
			keywords: [
				'models',
				'pull',
				'delete',
				'create',
				'edit',
				'modelfile',
				'gguf',
				'import',
				'export'
			]
		},
		{
			id: 'subagents',
			title: 'Sub-agents',
			route: '/admin/settings/subagents',
			keywords: ['sub-agents', 'subagents', 'delegation', 'background', 'agents']
		},
		{
			id: 'evaluations',
			title: 'Evaluations',
			route: '/admin/settings/evaluations',
			keywords: ['evaluations', 'feedback', 'rating', 'arena', 'leaderboard', 'preference']
		},
		{
			id: 'analytics',
			title: 'Analytics',
			route: '/admin/settings/analytics',
			keywords: ['analytics', 'usage', 'stats', 'dashboard', 'models', 'users', 'messages']
		},
		{
			id: 'integrations',
			title: 'Integrations',
			route: '/admin/settings/integrations',
			keywords: [
				'tools',
				'integrations',
				'plugins',
				'extensions',
				'functions',
				'openapi',
				'server',
				'knowledge',
				'vector db',
				'qdrant',
				'rag',
				'retrieval',
				'sources'
			]
		},
		{
			id: 'documents',
			title: 'Documents',
			route: '/admin/settings/documents',
			keywords: [
				'documents',
				'files',
				'rag',
				'knowledge',
				'upload',
				'embedding',
				'vector db',
				'chunk',
				'overlap',
				'splitter',
				'pdf',
				'ocr',
				'tika',
				'docling',
				'unstructured'
			]
		},
		{
			id: 'web',
			title: 'Web Search',
			route: '/admin/settings/web',
			keywords: [
				'web search',
				'google',
				'bing',
				'duckduckgo',
				'serp',
				'searxng',
				'moojeh',
				'yacy',
				'serper',
				'serply',
				'tavily',
				'exa',
				'perplexity',
				'firecrawl'
			]
		},
		{
			id: 'code-execution',
			title: 'Code Execution',
			route: '/admin/settings/code-execution',
			keywords: ['code execution', 'python', 'sandbox', 'compiler', 'jupyter', 'interpreter']
		},
		{
			id: 'interface',
			title: 'Interface',
			route: '/admin/settings/interface',
			keywords: [
				'interface',
				'ui',
				'appearance',
				'banners',
				'tasks',
				'prompt suggestions',
				'title generation',
				'tags'
			]
		},
		{
			id: 'audio',
			title: 'Audio',
			route: '/admin/settings/audio',
			keywords: [
				'audio',
				'voice',
				'speech',
				'tts',
				'stt',
				'whisper',
				'deepgram',
				'azure',
				'openai',
				'elevenlabs'
			]
		},
		{
			id: 'images',
			title: 'Images',
			route: '/admin/settings/images',
			keywords: [
				'images',
				'generation',
				'dalle',
				'stable diffusion',
				'comfyui',
				'automatic1111',
				'gemini'
			]
		},
		{
			id: 'pipelines',
			title: 'Pipelines',
			route: '/admin/settings/pipelines',
			keywords: ['pipelines', 'workflows', 'filters', 'valves', 'middleware']
		},
		{
			id: 'db',
			title: 'Database',
			route: '/admin/settings/db',
			keywords: ['database', 'export', 'import', 'backup', 'chats', 'users']
		},
		{
			id: 'email',
			title: 'Email',
			route: '/admin/settings/email',
			keywords: ['email', 'registration', 'verification', 'smtp', 'templates', 'deliveries']
		},
		{
			id: 'update',
			title: 'Update',
			route: '/admin/settings/update',
			keywords: ['update', 'version', 'release', 'announcement', 'deployment']
		}
	];

	const setFilteredSettings = () => {
		filteredSettings = allSettings.filter((tab) => {
			const searchTerm = search.toLowerCase().trim();
			if (tab.id === 'analytics' && !analyticsEnabled) {
				return false;
			}

			return (
				search === '' ||
				tab.title.toLowerCase().includes(searchTerm) ||
				tab.keywords.some((keyword) => keyword.includes(searchTerm))
			);
		});
	};

	const searchDebounceHandler = () => {
		if (searchDebounceTimeout) {
			clearTimeout(searchDebounceTimeout);
		}

		searchDebounceTimeout = setTimeout(() => {
			setFilteredSettings();
		}, 100);
	};

	const tabButtonClass = (active) =>
		`flex items-center gap-1.5 h-7 px-2 md:w-full shrink-0 rounded-lg text-xs text-left transition-colors duration-75 select-none ${
			active
				? 'font-medium text-gray-900 dark:text-white bg-gray-100 dark:bg-white/6'
				: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
		}`;

	onMount(() => {
		const containerElement = document.getElementById('admin-settings-tabs-container');

		if (containerElement) {
			containerElement.addEventListener('wheel', function (event) {
				if (event.deltaY !== 0) {
					// Adjust horizontal scroll position based on vertical scroll
					containerElement.scrollLeft += event.deltaY;
				}
			});
		}

		setFilteredSettings();
		// Scroll to the selected tab on mount
		scrollToTab(selectedTab);
	});
</script>

<div class="flex flex-col md:flex-row w-full h-full min-h-0 pb-2">
	<nav
		id="admin-settings-tabs-container"
		class="shrink-0 min-w-0 md:min-h-0 flex md:block border-b md:border-b-0 md:border-r border-gray-100/30 dark:border-white/[0.02] md:w-[15rem]"
	>
		<div
			class="tabs flex min-w-0 flex-1 overflow-x-auto md:overflow-x-hidden md:overflow-y-auto md:flex-col p-1 gap-px"
		>
			{#if modal}
				<button
					type="button"
					class="flex h-7 shrink-0 items-center gap-1.5 rounded-lg px-2 text-xs text-gray-400 transition-colors hover:text-gray-700 dark:text-gray-600 dark:hover:text-gray-300 md:mb-0 md:w-full"
					on:click={() => dispatch('close')}
				>
					<ChevronLeft className="size-3" strokeWidth="2" />
					<span>{$i18n.t('Back')}</span>
				</button>
			{/if}

			<span class="hidden md:block text-[0.625rem] text-gray-400 dark:text-gray-600 px-2 mt-1 mb-1">
				{$i18n.t('Admin')}
			</span>

			<div
				class="hidden md:flex items-center gap-1.5 h-7 px-2 md:w-full shrink-0 rounded-lg text-xs bg-gray-50/70 dark:bg-white/[0.03] mb-2"
				id="settings-search"
			>
				<div class="self-center rounded-l-xl bg-transparent">
					<Search className="size-3.5" strokeWidth="1.5" />
				</div>
				<label class="sr-only" for="search-input-admin-settings">{$i18n.t('Search')}</label>
				<input
					class="w-full py-1 text-xs bg-transparent dark:text-gray-300 outline-hidden"
					bind:value={search}
					id="search-input-admin-settings"
					on:input={searchDebounceHandler}
					placeholder={$i18n.t('Search')}
				/>
			</div>

			<!-- {$i18n.t('General')} -->
			<!-- {$i18n.t('Platform')} -->
			<!-- {$i18n.t('Authentication')} -->
			<!-- {$i18n.t('Connections')} -->
			<!-- {$i18n.t('Models')} -->
			<!-- {$i18n.t('Sub-agents')} -->
			<!-- {$i18n.t('Evaluations')} -->
			<!-- {$i18n.t('Analytics')} -->
			<!-- {$i18n.t('Integrations')} -->
			<!-- {$i18n.t('Documents')} -->
			<!-- {$i18n.t('Web Search')} -->
			<!-- {$i18n.t('Code Execution')} -->
			<!-- {$i18n.t('Interface')} -->
			<!-- {$i18n.t('Audio')} -->
			<!-- {$i18n.t('Images')} -->
			<!-- {$i18n.t('Pipelines')} -->
			<!-- {$i18n.t('Database')} -->
			<!-- {$i18n.t('Email')} -->
			{#each filteredSettings as tab (tab.id)}
				{#if modal}
					<button
						id={tab.id}
						type="button"
						role="tab"
						aria-selected={selectedTab === tab.id}
						class={tabButtonClass(selectedTab === tab.id)}
						on:click={() => (selectedTab = tab.id)}
					>
						<AdminTabIcon id={tab.id} className="size-3.5" strokeWidth="2" />
						<div class="self-center truncate">{$i18n.t(tab.title)}</div>
					</button>
				{:else}
					<a
						id={tab.id}
						href={tab.route}
						draggable="false"
						class={tabButtonClass(selectedTab === tab.id)}
					>
						<AdminTabIcon id={tab.id} className="size-3.5" strokeWidth="2" />
						<div class="self-center truncate">{$i18n.t(tab.title)}</div>
					</a>
				{/if}
			{/each}
		</div>
	</nav>

	<div class="flex-1 min-h-0 p-4 md:px-5 flex flex-col">
		<div class="w-full h-full min-h-0 flex flex-col">
			<div class="flex-1 min-h-0 overflow-hidden">
				{#if selectedTab === 'platform'}
					<Platform />
				{:else if selectedTab === 'general'}
					<General
						saveHandler={async () => {
							toast.success($i18n.t('Settings saved successfully!'));

							await tick();
							await config.set(await getBackendConfig());
						}}
					/>
				{:else if selectedTab === 'update'}
					<Update />
				{:else if selectedTab === 'authentication'}
					<Authentication />
				{:else if selectedTab === 'connections'}
					<Connections
						on:save={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'models'}
					<Models bind:tabState />
				{:else if selectedTab === 'subagents'}
					<Subagents />
				{:else if selectedTab === 'evaluations'}
					<Evaluations />
				{:else if selectedTab === 'analytics' && analyticsEnabled}
					<Analytics />
				{:else if selectedTab === 'integrations'}
					<Integrations />
				{:else if selectedTab === 'documents'}
					<Documents
						on:save={async () => {
							toast.success($i18n.t('Settings saved successfully!'));

							await tick();
							await config.set(await getBackendConfig());
						}}
					/>
				{:else if selectedTab === 'web'}
					<WebSearch
						saveHandler={async () => {
							toast.success($i18n.t('Settings saved successfully!'));

							await tick();
							await config.set(await getBackendConfig());
						}}
					/>
				{:else if selectedTab === 'code-execution'}
					<CodeExecution
						saveHandler={async () => {
							toast.success($i18n.t('Settings saved successfully!'));

							await tick();
							await config.set(await getBackendConfig());
						}}
					/>
				{:else if selectedTab === 'interface'}
					<Interface
						on:save={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'audio'}
					<Audio
						saveHandler={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'images'}
					<Images
						on:save={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'db'}
					<Database
						saveHandler={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'pipelines'}
					<Pipelines
						saveHandler={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'email'}
					<Email />
				{/if}
			</div>
		</div>
	</div>
</div>
