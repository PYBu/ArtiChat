import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();

const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const failures = [];

const packageJson = JSON.parse(read('package.json'));
const expectedVersion = packageJson.version;
const expectedDisplayVersion = `${expectedVersion} (Artivis Alpha)`;
const requestedTag = process.argv.find((value) => value.startsWith('--tag='))?.slice('--tag='.length);

if (requestedTag && requestedTag.replace(/^v/, '') !== expectedVersion) {
	failures.push(`release tag ${requestedTag} does not match package version ${expectedVersion}`);
}

const packageLock = JSON.parse(read('package-lock.json'));
if (packageLock.version !== expectedVersion) {
	failures.push(`package-lock.json root version is ${packageLock.version}, expected ${expectedVersion}`);
}
if (packageLock.packages?.['']?.version !== expectedVersion) {
	failures.push(
		`package-lock.json package root version is ${packageLock.packages?.['']?.version}, expected ${expectedVersion}`
	);
}

const constants = read('src/lib/constants.ts');
if (!constants.includes(`export const WEBUI_VERSION = APP_VERSION;`)) {
	failures.push('WEBUI_VERSION must remain the semantic APP_VERSION value');
}
if (!constants.includes('export const WEBUI_DISPLAY_VERSION = `${WEBUI_VERSION} (Artivis Alpha)`;')) {
	failures.push('WEBUI_DISPLAY_VERSION must derive from WEBUI_VERSION');
}

const about = read('src/lib/components/chat/Settings/About.svelte');
if (!about.includes('WEBUI_DISPLAY_VERSION')) {
	failures.push('About page must render WEBUI_DISPLAY_VERSION');
}

const changelogModal = read('src/lib/components/ChangelogModal.svelte');
if (!changelogModal.includes('WEBUI_DISPLAY_VERSION')) {
	failures.push('Changelog modal must render WEBUI_DISPLAY_VERSION');
}

const main = read('backend/open_webui/main.py');
if (!main.includes(`DISPLAY_VERSION = f'{VERSION} (Artivis Alpha)'`)) {
	failures.push('backend changelog must define the Artivis Alpha display version');
}
if (!main.includes('DISPLAY_VERSION: {')) {
	failures.push('backend changelog must use DISPLAY_VERSION as the displayed release key');
}

const dockerfile = read('Dockerfile');
if (!dockerfile.includes('ENV WEBUI_BUILD_HASH=${BUILD_HASH}')) {
	failures.push('Docker image must expose BUILD_HASH as WEBUI_BUILD_HASH');
}
if (dockerfile.includes('ENV WEBUI_BUILD_VERSION=${BUILD_HASH}')) {
	failures.push('Docker image still uses the unread WEBUI_BUILD_VERSION variable');
}

if (failures.length > 0) {
	for (const failure of failures) {
		console.error(failure);
	}
	process.exit(1);
}

console.log(`Release version guard passed: v${expectedDisplayVersion}`);
