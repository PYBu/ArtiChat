export type DirectConnections = {
	OPENAI_API_BASE_URLS: string[];
	OPENAI_API_KEYS: string[];
	OPENAI_API_CONFIGS: Record<string, unknown>;
};

const STORAGE_KEY_PREFIX = 'artichat.direct-connections.v1';

const getStorageKey = (token: string): string | null => {
	try {
		const payload = token.split('.')[1];
		if (!payload) return null;
		const padded = payload
			.replace(/-/g, '+')
			.replace(/_/g, '/')
			.padEnd(Math.ceil(payload.length / 4) * 4, '=');
		const userId = JSON.parse(atob(padded))?.id;
		return typeof userId === 'string' && userId
			? `${STORAGE_KEY_PREFIX}.${encodeURIComponent(userId)}`
			: null;
	} catch {
		return null;
	}
};

const normalizeDirectConnections = (value: unknown): DirectConnections | null => {
	if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
	const candidate = value as Partial<DirectConnections>;
	if (!Array.isArray(candidate.OPENAI_API_BASE_URLS) || !Array.isArray(candidate.OPENAI_API_KEYS)) {
		return null;
	}

	const urls = candidate.OPENAI_API_BASE_URLS.filter(
		(item): item is string => typeof item === 'string'
	);
	const keys = candidate.OPENAI_API_KEYS.filter((item): item is string => typeof item === 'string');
	if (
		urls.length !== candidate.OPENAI_API_BASE_URLS.length ||
		keys.length !== candidate.OPENAI_API_KEYS.length
	) {
		return null;
	}
	if (urls.length > 32 || keys.length > 32 || urls.some((url) => url.length > 2048)) return null;

	const configs = candidate.OPENAI_API_CONFIGS;
	return {
		OPENAI_API_BASE_URLS: urls,
		OPENAI_API_KEYS: keys,
		OPENAI_API_CONFIGS:
			configs && typeof configs === 'object' && !Array.isArray(configs) ? { ...configs } : {}
	};
};

export const loadDirectConnections = (token: string): DirectConnections | null => {
	if (typeof localStorage === 'undefined') return null;
	const storageKey = getStorageKey(token);
	if (!storageKey) return null;
	try {
		return normalizeDirectConnections(JSON.parse(localStorage.getItem(storageKey) ?? 'null'));
	} catch {
		return null;
	}
};

export const saveDirectConnections = (token: string, value: unknown): void => {
	if (typeof localStorage === 'undefined') return;
	const storageKey = getStorageKey(token);
	if (!storageKey) return;
	const normalized = normalizeDirectConnections(value);
	if (normalized) {
		localStorage.setItem(storageKey, JSON.stringify(normalized));
	} else {
		localStorage.removeItem(storageKey);
	}
};

export const mergeLocalDirectConnections = (token: string, settings: any): any => {
	const local = loadDirectConnections(token);
	if (!settings || typeof settings !== 'object') {
		return local ? { ui: { directConnections: local } } : settings;
	}

	return {
		...settings,
		ui: {
			...(settings.ui ?? {}),
			...(local ? { directConnections: local } : {})
		}
	};
};

export const prepareUserSettingsForServer = (token: string, settings: any): any => {
	if (!settings || typeof settings !== 'object') return settings;
	const next = { ...settings };
	if (next.ui && typeof next.ui === 'object' && !Array.isArray(next.ui)) {
		const { directConnections, ...serverUi } = next.ui;
		if (directConnections !== undefined) saveDirectConnections(token, directConnections);
		next.ui = serverUi;
	}
	return next;
};
