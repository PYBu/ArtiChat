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
	'src/lib/components/chat/Settings/Integrations/Terminals.svelte'
];

const forbidden = [
	'Open WebUI',
	'OpenWebUI',
	'Open Terminal',
	'open-webui',
	'Open_WebUI',
	'openwebui.com',
	'docs.openwebui.com',
	'github.com/open-webui'
];

const root = process.cwd();
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
