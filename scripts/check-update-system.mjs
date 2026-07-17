import fs from 'node:fs';

const panelPath = 'src/lib/components/admin/Settings/VersionUpdatePanel.svelte';
const pagePath = 'src/lib/components/admin/Settings/Update.svelte';
const settingsPath = 'src/lib/components/admin/Settings.svelte';
const generalPath = 'src/lib/components/admin/Settings/General.svelte';

if (!fs.existsSync(panelPath)) {
	throw new Error(`Version update panel is missing: ${panelPath}`);
}

for (const path of [pagePath, settingsPath, generalPath]) {
	if (!fs.existsSync(path)) throw new Error(`Update settings file is missing: ${path}`);
}

const page = fs.readFileSync(pagePath, 'utf8');
for (const required of ['VersionUpdatePanel', 'getUpdateAnnouncement', '暂无公告']) {
	if (!page.includes(required)) throw new Error(`Update settings page is missing ${required}`);
}

const settings = fs.readFileSync(settingsPath, 'utf8');
for (const required of ["id: 'update'", "route: '/admin/settings/update'", '<Update />']) {
	if (!settings.includes(required)) throw new Error(`Admin settings is missing ${required}`);
}

const general = fs.readFileSync(generalPath, 'utf8');
if (general.includes('VersionUpdatePanel')) {
	throw new Error('Version update panel must not remain in General settings');
}

const appLayout = fs.readFileSync('src/routes/(app)/+layout.svelte', 'utf8');
for (const forbidden of ['UpdateInfoToast', 'checkForVersionUpdates']) {
	if (appLayout.includes(forbidden)) {
		throw new Error(`Global update notification remains in app layout: ${forbidden}`);
	}
}

const announcementFiles = [
	'backend/open_webui/utils/announcement_service.py',
	'backend/open_webui/tests/updates/test_announcement_service.py'
];
for (const path of announcementFiles) {
	if (!fs.existsSync(path)) throw new Error(`Announcement service file is missing: ${path}`);
}

const announcementService = fs.readFileSync(announcementFiles[0], 'utf8');
for (const required of [
	"parsed.scheme != 'https'",
	'MAX_RESPONSE_BYTES',
	'cache_ttl_seconds',
	'normalize_announcement'
]) {
	if (!announcementService.includes(required)) {
		throw new Error(`Announcement service is missing ${required}`);
	}
}

const updateRouter = fs.readFileSync('backend/open_webui/routers/updates.py', 'utf8');
if (!updateRouter.includes("@router.get('/announcement')")) {
	throw new Error('Update router is missing the announcement endpoint');
}

const env = fs.readFileSync('backend/open_webui/env.py', 'utf8');
for (const required of [
	'ARTICHAT_ANNOUNCEMENT_URL',
	"https://artichatupdate.artivis.cc/index.json",
	'ARTICHAT_ANNOUNCEMENT_CACHE_TTL_SECONDS',
	'ARTICHAT_ANNOUNCEMENT_TIMEOUT_SECONDS'
]) {
	if (!env.includes(required)) throw new Error(`Environment config is missing ${required}`);
}
if (env.includes("os.getenv('ARTICHAT_ANNOUNCEMENT_URL'")) {
	throw new Error('The official announcement URL must not be environment-overridable');
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
for (const required of [
	'visudo -cf',
	'no-agent-forwarding',
	'no-port-forwarding',
	'no-X11-forwarding',
	'no-pty'
]) {
	if (!installer.includes(required))
		throw new Error(`Update runner installer is missing ${required}`);
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
if (compose.includes('/var/run/docker.sock'))
	throw new Error('Production Compose exposes the Docker socket');

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

const requiredWorkflows = [
	'.github/workflows/artichat-release.yml',
	'.github/workflows/artichat-deploy.yml'
];
const forbiddenWorkflows = [
	'.github/workflows/docker.yaml',
	'.github/workflows/release.yml',
	'.github/workflows/release-pypi.yml'
];
const workflowFailures = [];
for (const workflow of requiredWorkflows) {
	if (!fs.existsSync(workflow)) workflowFailures.push(`required workflow is missing: ${workflow}`);
}
for (const workflow of forbiddenWorkflows) {
	if (fs.existsSync(workflow))
		workflowFailures.push(`upstream publication workflow remains: ${workflow}`);
}
if (workflowFailures.length > 0) {
	throw new Error(workflowFailures.join('\n'));
}

const releaseWorkflow = fs.readFileSync('.github/workflows/artichat-release.yml', 'utf8');
for (const required of [
	'name: ArtiChat Release',
	"tags:\n      - 'v*.*.*'",
	'contents: write',
	'packages: write',
	'artichat-release-${{ github.ref }}',
	'GITHUB_REPOSITORY,,',
	'npm ci --force',
	'npm run test:release-version',
	'npm run test:branding',
	'npm run test:subscriptions',
	'npm run test:updates',
	'npm run test:frontend',
	'npm run build',
	'ghcr.io',
	'GITHUB_TOKEN',
	'linux/amd64',
	'BUILD_HASH=${GITHUB_SHA}',
	'docker buildx imagetools inspect',
	'gh release create'
]) {
	if (!releaseWorkflow.includes(required))
		throw new Error(`ArtiChat release workflow is missing ${required}`);
}
if (releaseWorkflow.includes('workflow_dispatch:'))
	throw new Error('ArtiChat release workflow must be tag-driven');
const inspectIndex = releaseWorkflow.indexOf('docker buildx imagetools inspect');
const releaseIndex = releaseWorkflow.indexOf('gh release create');
if (releaseIndex < inspectIndex)
	throw new Error('GitHub Release must be created after image inspection');

const deployWorkflow = fs.readFileSync('.github/workflows/artichat-deploy.yml', 'utf8');
for (const required of [
	'workflow_dispatch:',
	'version:',
	'operation_id:',
	'artichat-production',
	'cancel-in-progress: false',
	'ARTICHAT_DEPLOY_KNOWN_HOSTS',
	'gh release view',
	'~/.ssh/artichat_deploy',
	'deploy ${VERSION} ${OPERATION_ID}'
]) {
	if (!deployWorkflow.includes(required))
		throw new Error(`ArtiChat deploy workflow is missing ${required}`);
}
if (/:latest\b/.test(deployWorkflow) || deployWorkflow.includes('StrictHostKeyChecking=no')) {
	throw new Error(
		'ArtiChat deploy workflow contains an unsafe deployment target or host-key setting'
	);
}

const workflowFiles = fs
	.readdirSync('.github/workflows')
	.filter((name) => /\.(yml|yaml)$/.test(name));
for (const file of workflowFiles) {
	const workflow = fs.readFileSync(`.github/workflows/${file}`, 'utf8');
	for (const forbidden of [
		'pull_request_target',
		'docker.sock',
		'docker.io',
		'openwebui',
		'open-webui'
	]) {
		if (workflow.includes(forbidden))
			throw new Error(
				`Workflow ${file} contains forbidden publication or privilege string: ${forbidden}`
			);
	}
}

console.log('Update system guard passed.');
