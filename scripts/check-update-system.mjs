import fs from 'node:fs';

const panelPath = 'src/lib/components/admin/Settings/VersionUpdatePanel.svelte';

if (!fs.existsSync(panelPath)) {
	throw new Error(`Version update panel is missing: ${panelPath}`);
}

const panel = fs.readFileSync(panelPath, 'utf8');
for (const required of [
	'getUpdateInfo',
	'getUpdateStatus',
	'deployUpdate',
	'ConfirmDialog',
	'shouldPollUpdate'
]) {
	if (!panel.includes(required)) {
		throw new Error(`Version update panel is missing ${required}`);
	}
}

console.log('Update system guard passed.');
