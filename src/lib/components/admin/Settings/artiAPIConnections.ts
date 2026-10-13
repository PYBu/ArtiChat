export const ARTIAPI_BASE_URL = 'https://api.artivis.cc/v1';

export type OpenAIProviderConfig = {
	ENABLE_OPENAI_API: boolean;
	OPENAI_API_BASE_URLS: string[];
	OPENAI_API_KEYS: string[];
	OPENAI_API_CONFIGS: Record<string, Record<string, unknown>>;
};

export type ArtiAPIKeyConfig = {
	key: string;
	originalKey?: string;
	config: Record<string, unknown>;
};

export const isArtiAPIUrl = (url: string) => url.replace(/\/+$/, '') === ARTIAPI_BASE_URL;

const getConnectionConfig = (config: OpenAIProviderConfig, index: number) =>
	config.OPENAI_API_CONFIGS[String(index)] ??
	config.OPENAI_API_CONFIGS[config.OPENAI_API_BASE_URLS[index]] ??
	{};

export const getArtiAPIKeys = (config: OpenAIProviderConfig): ArtiAPIKeyConfig[] =>
	config.OPENAI_API_BASE_URLS.flatMap((url, index) =>
		isArtiAPIUrl(url)
			? [
					{
						key: config.OPENAI_API_KEYS[index] ?? '',
						config: { ...getConnectionConfig(config, index) }
					}
				]
			: []
	);

// Rebuild index-based configuration together with the URL and key arrays when keys are removed.
export const mergeArtiAPIKeys = (
	current: OpenAIProviderConfig,
	keys: ArtiAPIKeyConfig[]
): OpenAIProviderConfig => {
	const existing = getArtiAPIKeys(current);
	const result: OpenAIProviderConfig = {
		ENABLE_OPENAI_API:
			current.ENABLE_OPENAI_API || keys.some((entry) => entry.config.enable !== false),
		OPENAI_API_BASE_URLS: [],
		OPENAI_API_KEYS: [],
		OPENAI_API_CONFIGS: {}
	};

	const append = (url: string, key: string, config: Record<string, unknown>) => {
		const index = result.OPENAI_API_BASE_URLS.length;
		result.OPENAI_API_BASE_URLS.push(url);
		result.OPENAI_API_KEYS.push(key);
		result.OPENAI_API_CONFIGS[String(index)] = { ...config };
	};
	const appendArtiAPIKey = (entry: ArtiAPIKeyConfig) => {
		const previous = existing.find((stored) => stored.key === (entry.originalKey ?? entry.key));
		append(ARTIAPI_BASE_URL, entry.key.trim(), { ...previous?.config, ...entry.config });
	};

	let nextKey = 0;
	current.OPENAI_API_BASE_URLS.forEach((url, index) => {
		if (isArtiAPIUrl(url)) {
			if (nextKey < keys.length) appendArtiAPIKey(keys[nextKey++]);
		} else {
			append(url, current.OPENAI_API_KEYS[index] ?? '', getConnectionConfig(current, index));
		}
	});
	keys.slice(nextKey).forEach(appendArtiAPIKey);
	return result;
};
