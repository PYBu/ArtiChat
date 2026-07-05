import fs from 'node:fs';
import path from 'node:path';

const files = [
	'src/app.html',
	'src/lib/constants.ts',
	'src/routes/+layout.svelte',
	'src/lib/components/channel/Channel.svelte',
	'src/lib/components/chat/Settings/About.svelte',
	'src/lib/components/admin/Settings/General.svelte',
	'src/lib/components/layout/UpdateInfoToast.svelte',
	'src/lib/components/layout/Sidebar/UserMenu.svelte',
	'src/lib/components/chat/Settings/General.svelte',
	'src/routes/error/+page.svelte',
	'static/static/site.webmanifest',
	'backend/open_webui/static/site.webmanifest',
	'static/opensearch.xml',
	'backend/open_webui/env.py',
	'backend/open_webui/main.py',
	'backend/open_webui/constants.py',
	'backend/open_webui/events.py',
	'backend/open_webui/utils/automations.py',
	'backend/open_webui/routers/audio.py',
	'backend/open_webui/routers/openai.py',
	'backend/open_webui/utils/oauth.py',
	'docker-compose.yaml',
	'.env.example',
	'src/lib/components/workspace/Models.svelte',
	'src/lib/components/workspace/Prompts.svelte',
	'src/lib/components/workspace/Tools.svelte',
	'src/lib/components/admin/Functions.svelte',
	'src/lib/components/admin/Evaluations/Feedbacks.svelte',
	'src/lib/components/chat/ShareChatModal.svelte',
	'src/lib/components/chat/Settings/SyncStatsModal.svelte',
	'src/lib/components/workspace/common/ManifestModal.svelte',
	'src/lib/components/chat/ToolServersModal.svelte',
	'src/lib/components/admin/Settings/Audio.svelte',
	'src/lib/components/admin/Settings/Events.svelte',
	'src/lib/components/admin/Settings/ExternalKnowledge.svelte',
	'src/lib/components/chat/Settings/Connections.svelte',
	'src/lib/components/chat/Settings/Integrations.svelte',
	'src/lib/components/chat/Settings/Integrations/Terminals.svelte',
	'src/lib/components/AddToolServerModal.svelte',
	'src/lib/components/admin/Users/UserList.svelte',
	'src/lib/components/chat/ChatPlaceholder.svelte',
	'backend/open_webui/retrieval/web/external.py',
	'backend/open_webui/retrieval/web/perplexity.py',
	'src/routes/(app)/workspace/tools/create/+page.svelte',
	'src/routes/(app)/admin/functions/create/+page.svelte',
	'src/routes/(app)/workspace/prompts/create/+page.svelte',
	'src/routes/(app)/workspace/models/create/+page.svelte',
	'src/routes/(app)/workspace/tools/edit/+page.svelte',
	'src/routes/(app)/admin/functions/edit/+page.svelte',
	'src/lib/components/chat/Placeholder.svelte',
	'src/lib/components/AddTerminalServerModal.svelte',
	'src/lib/utils/connections.ts',
	'src/lib/components/admin/Functions/FunctionEditor.svelte',
	'src/lib/components/chat/FileNav.svelte',
	'src/lib/components/workspace/Models/Capabilities.svelte',
	'src/lib/components/workspace/Knowledge/KnowledgeBase.svelte',
	'src/lib/components/admin/Settings/Authentication.svelte',
	'src/lib/components/admin/Settings/Documents.svelte',
	'src/lib/components/admin/Settings/Connections.svelte',
	'src/lib/components/admin/Settings/Integrations.svelte',
	'src/lib/components/chat/Messages/RateComment.svelte',
	'src/lib/components/chat/ModelSelector/ModelItemMenu.svelte',
	'src/lib/components/layout/Sidebar/RecursiveFolder.svelte',
	'src/lib/components/layout/Sidebar/PinnedNoteList.svelte',
	'src/lib/components/layout/Sidebar/ChatItem.svelte',
	'src/lib/components/chat/MessageInput.svelte',
	'src/lib/components/chat/XTerminal.svelte',
	'src/lib/apis/configs/index.ts',
	'backend/open_webui/routers/files.py',
	'backend/open_webui/utils/headers.py',
	'backend/open_webui/utils/memory.py',
	'backend/open_webui/retrieval/vector/dbs/pinecone.py',
	'backend/start.sh',
	'backend/open_webui/__init__.py',
	'backend/open_webui/config.py',
	'backend/open_webui/retrieval/web/yandex.py',
	'backend/open_webui/retrieval/web/yacy.py',
	'backend/open_webui/retrieval/web/searxng.py',
	'backend/open_webui/retrieval/web/perplexity_search.py',
	'backend/open_webui/retrieval/web/serply.py',
	'backend/open_webui/retrieval/loaders/mistral.py',
	'backend/open_webui/retrieval/loaders/external_web.py',
	'package.json',
	'package-lock.json',
	'pyproject.toml',
	'uv.lock'
];

const addTranslationFiles = (dir) => {
	if (!fs.existsSync(dir)) {
		return;
	}

	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		const entryPath = path.join(dir, entry.name);

		if (entry.isDirectory()) {
			addTranslationFiles(entryPath);
		} else if (entry.name === 'translation.json') {
			files.push(path.relative(root, entryPath).replaceAll(path.sep, '/'));
		}
	}
};

const forbidden = [
	'Open WebUI',
	'OpenWebUI',
	'OpenTerminal',
	'Open Terminal',
	'open-webui',
	'Open_WebUI',
	'openwebui.com',
	'docs.openwebui.com',
	'github.com/open-webui'
];

const root = process.cwd();
addTranslationFiles(path.join(root, 'src/lib/i18n/locales'));
const missingFiles = [];
const findings = [];

for (const file of files) {
	const filePath = path.join(root, file);

	if (!fs.existsSync(filePath)) {
		missingFiles.push(file);
		continue;
	}

	const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/);

	for (const [index, line] of lines.entries()) {
		for (const label of forbidden) {
			if (line.includes(label)) {
				findings.push(`${file}:${index + 1}: forbidden ${label}: ${line.trim()}`);
			}
		}
	}
}

if (missingFiles.length > 0) {
	console.error('Missing files:');

	for (const file of missingFiles) {
		console.error(file);
	}
}

for (const finding of findings) {
	console.error(finding);
}

if (missingFiles.length > 0 || findings.length > 0) {
	process.exit(1);
}

console.log(`Branding scan passed for ${files.length} files.`);
