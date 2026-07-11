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

for (const forbidden of ['--volumes', 'docker system prune', '/var/run/docker.sock']) {
	if (deploy.includes(forbidden)) {
		throw new Error(`Deployment script contains forbidden operation: ${forbidden}`);
	}
}

const runnerFiles = [
	'deploy/aws-1panel/artichat-deploy-ssh.sh',
	'deploy/aws-1panel/install-update-runner.sh',
	'deploy/aws-1panel/docker-compose.artichat-prod.yaml'
];
for (const path of runnerFiles) {
	if (!fs.existsSync(path)) throw new Error(`Update runner file is missing: ${path}`);
}

const sshWrapper = fs.readFileSync(runnerFiles[0], 'utf8');
for (const required of ['SSH_ORIGINAL_COMMAND', 'exec sudo /usr/local/sbin/artichat-deploy']) {
	if (!sshWrapper.includes(required)) throw new Error(`SSH wrapper is missing ${required}`);
}

const installer = fs.readFileSync(runnerFiles[1], 'utf8');
for (const required of ['visudo -cf', 'no-agent-forwarding', 'no-port-forwarding', 'no-X11-forwarding', 'no-pty']) {
	if (!installer.includes(required)) throw new Error(`Update runner installer is missing ${required}`);
}

const compose = fs.readFileSync(runnerFiles[2], 'utf8');
for (const required of [
	'${ARTICHAT_IMAGE:?ARTICHAT_IMAGE is required}',
	'/data/artichat-prod/data:/app/backend/data',
	'/data/artichat-prod/update-state:/app/backend/data/update-state',
	'ARTICHAT_UPDATE_GITHUB_TOKEN'
]) {
	if (!compose.includes(required)) throw new Error(`Production Compose is missing ${required}`);
}
if (compose.includes('/var/run/docker.sock')) throw new Error('Production Compose exposes the Docker socket');

const deploymentReadme = fs.readFileSync('deploy/aws-1panel/README.zh-CN.md', 'utf8');
for (const required of [
	'--env-file .env --env-file image.env -f docker-compose.yaml ps',
	'curl -fsS http://127.0.0.1:13000/health',
	'curl -fsS http://127.0.0.1:13000/api/version',
	'/data/artichat-prod/backups',
	'image.env',
	'docker system prune --volumes'
]) {
	if (!deploymentReadme.includes(required)) {
		throw new Error(`Production deployment README is missing ${required}`);
	}
}

console.log('Update system guard passed.');
