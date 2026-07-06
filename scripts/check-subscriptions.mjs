import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const exists = (file) => fs.existsSync(path.join(root, file));
const failures = [];

const requiredFiles = [
	'src/lib/apis/subscriptions/index.ts',
	'src/lib/components/chat/Settings/Subscription.svelte',
	'src/lib/components/chat/Settings/RedeemCode.svelte',
	'src/lib/components/chat/Settings/Usage.svelte',
	'src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte',
	'src/lib/components/admin/Settings/Subscriptions.svelte',
	'src/lib/components/workspace/Models/SubscriptionPolicy.svelte'
];

for (const file of requiredFiles) {
	if (!exists(file)) failures.push(`Missing ${file}`);
}

if (exists('src/lib/apis/subscriptions/index.ts')) {
	const api = read('src/lib/apis/subscriptions/index.ts');
	for (const name of [
		'getMySubscription',
		'getMySubscriptionUsage',
		'redeemSubscriptionCode',
		'updateBillingAddress',
		'getAdminSubscriptionPlans',
		'createAdminRedemptionCodes'
	]) {
		if (!api.includes(`export const ${name}`)) failures.push(`Missing API helper ${name}`);
	}
}

if (failures.length > 0) {
	for (const failure of failures) console.error(failure);
	process.exit(1);
}

console.log('Subscription static guard passed.');
