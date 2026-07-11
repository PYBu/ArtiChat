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

const deployPath = 'deploy/aws-1panel/artichat-deploy.sh';
if (!fs.existsSync(deployPath)) {
	throw new Error(`Deployment script is missing: ${deployPath}`);
}

const deploy = fs.readFileSync(deployPath, 'utf8');
for (const required of [
	'flock',
	'--no-deps',
	'--force-recreate',
	'/health',
	'/api/version',
	'rolled_back',
	'rotate_backups'
]) {
	if (!deploy.includes(required)) {
		throw new Error(`Deployment script is missing ${required}`);
	}
}

console.log('Update system guard passed.');

for (const forbidden of ['--volumes', 'docker system prune', '/var/run/docker.sock']) {
	if (deploy.includes(forbidden)) {
		throw new Error(`Deployment script contains forbidden operation: ${forbidden}`);
	}
}
