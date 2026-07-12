import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const exists = (file) => fs.existsSync(path.join(root, file));
const failures = [];

const requiredFiles = [
	'src/lib/apis/subscriptions/index.ts',
	'src/lib/apis/announcements/index.ts',
	'src/lib/components/chat/Settings/Subscription.svelte',
	'src/lib/components/chat/Settings/RedeemCode.svelte',
	'src/lib/components/chat/Settings/Usage.svelte',
	'src/lib/components/AnnouncementModal.svelte',
	'src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte',
	'src/lib/components/admin/Settings/Subscriptions.svelte',
	'src/lib/components/admin/Settings/Subscriptions/GiftCards.svelte',
	'src/lib/components/admin/Settings/Subscriptions/Announcements.svelte',
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
		'getSubscriptionPlans',
		'redeemSubscriptionCode',
		'getPendingGiftCards',
		'claimGiftCard',
		'updateBillingAddress',
		'getAdminSubscriptionPlans',
		'createAdminRedemptionCodes',
		'deleteAdminRedemptionCode',
		'createAdminGiftCards',
		'revokeAdminGiftCard'
	]) {
		if (!api.includes(`export const ${name}`)) failures.push(`Missing API helper ${name}`);
	}
}

if (exists('src/lib/apis/announcements/index.ts')) {
	const api = read('src/lib/apis/announcements/index.ts');
	for (const name of [
		'getActiveAnnouncements',
		'markAnnouncementViewed',
		'getAdminAnnouncements',
		'createAdminAnnouncement',
		'updateAdminAnnouncement',
		'deleteAdminAnnouncement'
	]) {
		if (!api.includes(`export const ${name}`)) failures.push(`Missing announcement API helper ${name}`);
	}
	if (!api.includes('include_inactive')) failures.push('Announcement API must expose include_inactive');
}

const adminAnnouncements = read('src/lib/components/admin/Settings/Subscriptions/Announcements.svelte');
for (const marker of ['showInactive', '显示已停用', "toast.success('公告已删除。')"]) {
	if (!adminAnnouncements.includes(marker)) failures.push(`Announcement admin missing ${marker}`);
}

const settingsModal = read('src/lib/components/chat/SettingsModal.svelte');
for (const marker of [
	"import Subscription from './Settings/Subscription.svelte'",
	"import RedeemCode from './Settings/RedeemCode.svelte'",
	"import Usage from './Settings/Usage.svelte'",
	"id: 'subscription'",
	"id: 'redeem_code'",
	"id: 'usage'",
	'<Subscription',
	'<RedeemCode',
	'<Usage'
]) {
	if (!settingsModal.includes(marker)) failures.push(`Settings modal missing ${marker}`);
}

const account = read('src/lib/components/chat/Settings/Account.svelte');
if (!account.includes('BillingAddress')) failures.push('Account settings must include BillingAddress');

const userMenu = read('src/lib/components/layout/Sidebar/UserMenu.svelte');
if (!userMenu.includes('SubscriptionQuotaRing')) failures.push('UserMenu must include SubscriptionQuotaRing');

const ring = read('src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte');
for (const marker of ['用量 / Usage', 'Plan Chatpoint', 'Check Chatpoint', 'refreshSubscription', 'exhausted', 'stroke-red']) {
	if (!ring.includes(marker)) failures.push(`Quota ring missing ${marker}`);
}

if (ring.includes('免费版')) failures.push('Quota ring must use Free instead of 免费版');

const adminSettings = read('src/lib/components/admin/Settings.svelte');
for (const marker of ['订阅管理', "selectedTab === 'subscriptions'", '<Subscriptions']) {
	if (!adminSettings.includes(marker)) failures.push(`Admin settings missing ${marker}`);
}

const adminSubscriptions = read('src/lib/components/admin/Settings/Subscriptions.svelte');
for (const marker of ['礼品卡', '公告', '<GiftCards', '<Announcements']) {
	if (!adminSubscriptions.includes(marker)) failures.push(`Admin subscriptions missing ${marker}`);
}

const redeemCode = read('src/lib/components/chat/Settings/RedeemCode.svelte');
for (const marker of ['你有待领取礼品卡', 'claimGiftCard', 'notifySubscriptionChanged']) {
	if (!redeemCode.includes(marker)) failures.push(`Redeem page missing ${marker}`);
}

const adminRedeemCodes = read('src/lib/components/admin/Settings/Subscriptions/RedeemCodes.svelte');
for (const marker of ['自定义兑换码', 'deleteAdminRedemptionCode', 'code.code ?? code.code_preview']) {
	if (!adminRedeemCodes.includes(marker)) failures.push(`Admin redeem codes missing ${marker}`);
}

const adminUsers = read('src/lib/components/admin/Settings/Subscriptions/UserSubscriptions.svelte');
for (const marker of ['邮箱、用户名、显示名或用户 ID', 'row.user?.email']) {
	if (!adminUsers.includes(marker)) failures.push(`Admin user subscriptions missing ${marker}`);
}

const usageLedger = read('src/lib/components/admin/Settings/Subscriptions/UsageLedger.svelte');
if (!usageLedger.includes('user?.email')) failures.push('Usage ledger must display user email');

const announcementModal = read('src/lib/components/AnnouncementModal.svelte');
for (const marker of ['getActiveAnnouncements', 'sessionStorage', 'markAnnouncementViewed']) {
	if (!announcementModal.includes(marker)) failures.push(`Announcement modal missing ${marker}`);
}

const modelEditor = read('src/lib/components/workspace/Models/ModelEditor.svelte');
if (!modelEditor.includes('SubscriptionPolicy')) failures.push('ModelEditor must include SubscriptionPolicy');

const editUser = read('src/lib/components/admin/Users/UserList/EditUserModal.svelte');
if (!editUser.includes('管理订阅')) failures.push('EditUserModal must link to subscription management');

if (failures.length > 0) {
	for (const failure of failures) console.error(failure);
	process.exit(1);
}

console.log('Subscription static guard passed.');
