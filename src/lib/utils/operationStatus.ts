export type OperationStatusEntry = {
	visible: boolean;
	text: string;
};

export type OperationStatusConfig = {
	enabled?: boolean;
	deduplicate?: boolean;
	entries?: Record<string, OperationStatusEntry>;
};

export type OperationStatus = {
	status_id?: string;
	action?: string;
	description?: string;
	display_description?: string;
	display_description_template?: string;
	display_description_custom?: boolean;
	done?: boolean;
	hidden?: boolean;
	error?: boolean | string;
	progress?: number;
	count?: number;
	urls?: string[];
	items?: unknown[];
	queries?: string[];
	query?: string;
	job_id?: string;
	[key: string]: unknown;
};

export type OperationStatusCatalogItem = {
	id: string;
	label: string;
	description: string;
	defaultText: string;
	group: string;
	visible: boolean;
};

// Memory maintenance is an internal side effect. It should not create a
// user-facing tool disclosure, while remaining present in the model output.
export const SILENT_MEMORY_TOOLS = new Set([
	'add_memory',
	'update_memory',
	'replace_memory_content',
	'delete_memory',
	'list_memories',
	'search_memories',
	'list_memory_paths',
	'read_memory_path'
]);

export const isSilentMemoryTool = (name: string | null | undefined): boolean =>
	SILENT_MEMORY_TOOLS.has(name?.trim().toLowerCase() ?? '');

const item = (
	id: string,
	label: string,
	description: string,
	group: string,
	visible = true,
	defaultText = ''
): OperationStatusCatalogItem => ({ id, label, description, group, visible, defaultText });

export const OPERATION_STATUS_CATALOG: OperationStatusCatalogItem[] = [
	item(
		'video.queued',
		'Video queued',
		'The video job is waiting to be processed.',
		'Video',
		false,
		'Video queued'
	),
	item(
		'video.submitting',
		'Submitting video',
		'The video request is being sent to the provider.',
		'Video',
		false,
		'Submitting video'
	),
	item(
		'video.running',
		'Video generating',
		'The provider is generating the video.',
		'Video',
		false,
		'Video generating'
	),
	item(
		'video.retrying',
		'Retrying video',
		'The video provider request is being retried.',
		'Video',
		false,
		'Retrying video'
	),
	item(
		'video.succeeded',
		'Video generated',
		'The video file is ready.',
		'Video',
		true,
		'Video generated'
	),
	item(
		'video.failed',
		'Video failed',
		'The video provider reported an error.',
		'Video',
		true,
		'Video failed'
	),
	item(
		'image.creating',
		'Creating image',
		'An image is being generated or edited.',
		'Image',
		true,
		'Creating image'
	),
	item(
		'image.succeeded',
		'Image created',
		'The image file is ready.',
		'Image',
		true,
		'Image created'
	),
	item(
		'image.failed',
		'Image failed',
		'The image provider reported an error.',
		'Image',
		true,
		'Image failed'
	),
	item('web_search.started', 'Searching the web', 'A web search has started.', 'Web Search'),
	item(
		'web_search.no_query',
		'No search query',
		'No usable search query was generated.',
		'Web Search'
	),
	item(
		'web_search.queries_generated',
		'Search queries generated',
		'Search queries are ready.',
		'Web Search'
	),
	item(
		'web_search.succeeded',
		'Web search completed',
		'Search results were retrieved.',
		'Web Search'
	),
	item(
		'web_search.no_results',
		'No search results',
		'The search returned no results.',
		'Web Search'
	),
	item('web_search.failed', 'Web search failed', 'The search request failed.', 'Web Search'),
	item(
		'retrieval.queries_generated',
		'Retrieval queries generated',
		'Knowledge retrieval queries are ready.',
		'Retrieval'
	),
	item(
		'retrieval.sources_retrieved',
		'Sources retrieved',
		'Knowledge sources were retrieved.',
		'Retrieval'
	),
	item('knowledge.searching', 'Searching knowledge', 'A knowledge search is running.', 'Retrieval'),
	item(
		'tool.executing',
		'Tool executing',
		'A tool call is running.',
		'Tools',
		true,
		'Executing {{NAME}}...'
	),
	item(
		'tool.completed',
		'Tool completed',
		'A tool call completed.',
		'Tools',
		true,
		'View Result from {{NAME}}'
	),
	item(
		'tool.failed',
		'Tool failed',
		'A tool call returned an error.',
		'Tools',
		true,
		'Tool failed'
	),
	item(
		'activity.exploring',
		'Exploring',
		'A grouped activity is running.',
		'Activity',
		true,
		'Exploring'
	),
	item(
		'activity.explored',
		'Explored',
		'A grouped activity completed.',
		'Activity',
		true,
		'Explored'
	),
	item(
		'code.analyzing',
		'Analyzing code',
		'Code analysis is running.',
		'Code',
		true,
		'Analyzing...'
	),
	item('code.analyzed', 'Code analyzed', 'Code analysis completed.', 'Code', true, 'Analyzed'),
	item('reasoning.thinking', 'Thinking', 'Reasoning is running.', 'Reasoning', true, 'Thinking...'),
	item('reasoning.thought', 'Thought', 'Reasoning completed.', 'Reasoning', true, 'Thought'),
	item(
		'reasoning.thought_short',
		'Short reasoning',
		'Reasoning completed in less than a second.',
		'Reasoning',
		true,
		'Thought for less than a second'
	),
	item(
		'reasoning.thought_seconds',
		'Reasoning duration in seconds',
		'Reasoning completed in seconds.',
		'Reasoning',
		true,
		'Thought for {{DURATION}} seconds'
	),
	item(
		'reasoning.thought_human',
		'Reasoning duration',
		'Reasoning completed in a humanized duration.',
		'Reasoning',
		true,
		'Thought for {{DURATION}}'
	)
];

export const OPERATION_STATUS_GROUPS = [
	...new Set(OPERATION_STATUS_CATALOG.map((item) => item.group))
].map((group) => ({
	group,
	items: OPERATION_STATUS_CATALOG.filter((item) => item.group === group)
}));

const fallbackEntry = (id: string): OperationStatusEntry => {
	const catalog = OPERATION_STATUS_CATALOG.find((item) => item.id === id);
	return {
		visible: catalog?.visible ?? true,
		text: catalog?.defaultText ?? ''
	};
};

export const getDefaultOperationStatusConfig = (): Required<OperationStatusConfig> => ({
	enabled: true,
	deduplicate: true,
	entries: Object.fromEntries(
		OPERATION_STATUS_CATALOG.map((item) => [
			item.id,
			{ visible: item.visible, text: item.defaultText }
		])
	)
});

export const getOperationStatusId = (status: OperationStatus | null | undefined): string | null => {
	if (!status) return null;
	if (typeof status.status_id === 'string' && status.status_id) return status.status_id;

	if (status.action === 'web_search') {
		if (status.error && status.description === 'No search results found')
			return 'web_search.no_results';
		if (status.error) return 'web_search.failed';
		if (status.done && (status.urls?.length || status.items?.length)) return 'web_search.succeeded';
		if (status.done && status.description === 'No search query generated')
			return 'web_search.no_query';
		return 'web_search.started';
	}
	if (status.action === 'web_search_queries_generated') return 'web_search.queries_generated';
	if (status.action === 'queries_generated') return 'retrieval.queries_generated';
	if (status.action === 'sources_retrieved') return 'retrieval.sources_retrieved';
	if (status.action === 'knowledge_search') return 'knowledge.searching';

	if (status.description === 'Creating image') return 'image.creating';
	if (status.description === 'Image created') return 'image.succeeded';
	if (status.description === 'An error occurred while generating an image') return 'image.failed';
	if (status.description?.includes('视频生成任务已排队')) return 'video.queued';
	if (status.description?.includes('正在提交视频生成任务')) return 'video.submitting';
	if (status.description?.includes('视频生成中')) return 'video.running';
	if (status.description?.includes('视频已生成')) return 'video.succeeded';
	if (status.description?.includes('视频生成将重试')) return 'video.retrying';
	if (status.description?.includes('视频生成失败')) return 'video.failed';

	// Older video events did not include a stable ID. Infer their terminal state
	// from the job fields so existing conversations receive the new defaults too.
	if (status.job_id || status.progress !== undefined) {
		if (status.error) return 'video.failed';
		if (status.done) return 'video.succeeded';
		if (status.progress && status.progress > 0) return 'video.running';
		return 'video.queued';
	}

	return status.action ? null : null;
};

export const getToolCallOperationStatusId = (
	name: string | null | undefined,
	done: boolean,
	failed = false
): string => {
	const normalizedName = name?.trim().toLowerCase();
	if (normalizedName === 'generate_image' || normalizedName === 'edit_image') {
		if (failed) return 'image.failed';
		return done ? 'image.succeeded' : 'image.creating';
	}
	if (normalizedName === 'generate_video') {
		if (failed) return 'video.failed';
		return done ? 'video.succeeded' : 'video.running';
	}
	if (failed) return 'tool.failed';
	return done ? 'tool.completed' : 'tool.executing';
};

/** Return a user-facing failure reason from a tool result without assuming one response shape. */
export const getToolCallFailureReason = (value: unknown, raw = ''): string => {
	const inspect = (candidate: unknown, depth = 0): string => {
		if (depth > 4 || candidate === null || candidate === undefined) return '';

		if (typeof candidate === 'string') {
			const text = candidate.trim();
			if (!text) return '';
			if (/^\s*(?:\[error\b|error\s*[:：]|failed\s*[:：])/i.test(text)) return text;
			if (depth < 4 && (text.startsWith('{') || text.startsWith('[') || text.startsWith('"'))) {
				try {
					return inspect(JSON.parse(text), depth + 1);
				} catch {
					return '';
				}
			}
			return '';
		}

		if (typeof candidate !== 'object' || Array.isArray(candidate)) return '';
		const record = candidate as Record<string, unknown>;
		if (record.error) {
			return typeof record.error === 'string' ? record.error : JSON.stringify(record.error);
		}
		const detailError = inspect(record.detail, depth + 1);
		if (detailError) return detailError;

		const status = String(record.status ?? '').toLowerCase();
		if (['error', 'failed', 'failure', 'cancelled', 'canceled', 'incomplete'].includes(status)) {
			const message = record.message ?? record.detail ?? status;
			return typeof message === 'string' ? message : JSON.stringify(message);
		}
		return '';
	};

	return inspect(value) || inspect(raw);
};

const interpolate = (template: string, status: OperationStatus): string => {
	const duration = Number(status.duration ?? 0);
	const values: Record<string, unknown> = {
		NAME: status.name ?? '',
		COUNT: status.count ?? status.urls?.length ?? status.items?.length ?? 0,
		DURATION: status.duration ?? '',
		ERROR: typeof status.error === 'string' ? status.error : (status.description ?? ''),
		QUERY: status.query ?? '',
		searchQuery: status.query ?? ''
	};
	if (duration >= 60 && values.DURATION !== '')
		values.DURATION = `${Math.round(duration / 60)} minutes`;
	return template.replace(/\{\{\s*([A-Za-z_]+)\s*\}\}/g, (_, key: string) =>
		String(values[key] ?? '')
	);
};

export const resolveOperationStatus = (
	status: OperationStatus,
	config: OperationStatusConfig | null | undefined
): OperationStatus => {
	const id = getOperationStatusId(status);
	const entry = (id && config?.entries?.[id]) || (id && fallbackEntry(id));
	const visible = (config?.enabled ?? true) && (entry?.visible ?? true) && status.hidden !== true;
	const catalog = id ? OPERATION_STATUS_CATALOG.find((item) => item.id === id) : undefined;
	const storedText = entry?.text?.trim();
	// Treat a persisted English catalog value as the built-in template so it can
	// still be localized in the user's current language.
	const customText = storedText && storedText !== catalog?.defaultText ? storedText : '';
	const displayTemplate = customText || catalog?.defaultText || '';
	return {
		...status,
		status_id: id ?? status.status_id,
		hidden: !visible,
		...(displayTemplate
			? {
					display_description: interpolate(displayTemplate, status),
					display_description_template: displayTemplate,
					display_description_custom: Boolean(customText)
				}
			: {})
	};
};

export const getVisibleOperationStatusHistory = (
	history: OperationStatus[] | null | undefined,
	config: OperationStatusConfig | null | undefined
): OperationStatus[] => {
	const visible = (history ?? [])
		.map((status) => resolveOperationStatus(status, config))
		.filter((status) => !status.hidden);
	if (!(config?.deduplicate ?? true)) return visible;

	return visible.reduce<OperationStatus[]>((next, status) => {
		const previous = next.at(-1);
		if (previous && sameStatusKey(previous, status) === sameStatusKey(status, previous)) {
			next[next.length - 1] = { ...previous, ...status };
		} else {
			next.push(status);
		}
		return next;
	}, []);
};

const sameStatusKey = (left: OperationStatus, right: OperationStatus): string =>
	getOperationStatusId(left) || left.action || left.description || '';

export const appendOperationStatus = (
	history: OperationStatus[] | null | undefined,
	status: OperationStatus,
	config: OperationStatusConfig | null | undefined
): OperationStatus[] => {
	const next = [...(history ?? [])];
	const previous = next.at(-1);
	if (
		previous &&
		(config?.deduplicate ?? true) &&
		sameStatusKey(previous, status) === sameStatusKey(status, previous)
	) {
		next[next.length - 1] = { ...previous, ...status };
		return next;
	}
	next.push(status);
	return next;
};
