import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const exists = (file) => fs.existsSync(path.join(root, file));
const failures = [];

const sourceFiles = (directory) =>
	fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
		const entryPath = path.join(directory, entry.name);
		if (entry.isDirectory()) return sourceFiles(entryPath);
		return /\.(svelte|ts)$/.test(entry.name) ? [entryPath] : [];
	});

const requiredFiles = [
	'src/lib/apis/subscriptions/index.ts',
	'src/lib/apis/announcements/index.ts',
	'src/lib/components/chat/Settings/Subscription.svelte',
	'src/lib/components/chat/Settings/RedeemCode.svelte',
	'src/lib/components/chat/Settings/Usage.svelte',
	'src/lib/components/chat/Settings/UsageCenter.svelte',
	'src/lib/components/chat/Settings/SubscriptionUsage.svelte',
	'src/lib/components/chat/Settings/SubscriptionCenter.svelte',
	'src/routes/(app)/account/subscription/+page.svelte',
	'src/lib/components/AnnouncementModal.svelte',
	'src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte',
	'src/lib/components/admin/Subscriptions/SubscriptionPageShell.svelte',
	'src/lib/components/admin/Subscriptions/SubscriptionHome.svelte',
	'src/routes/(app)/admin/subscriptions/+page.svelte',
	'src/routes/(app)/admin/subscriptions/plans/+page.svelte',
	'src/routes/(app)/admin/subscriptions/models/+page.svelte',
	'src/routes/(app)/admin/subscriptions/redeem-codes/+page.svelte',
	'src/routes/(app)/admin/subscriptions/gift-cards/+page.svelte',
	'src/routes/(app)/admin/subscriptions/announcements/+page.svelte',
	'src/routes/(app)/admin/subscriptions/usage/+page.svelte',
	'src/lib/components/admin/Settings/Subscriptions/GiftCards.svelte',
	'src/lib/components/admin/Settings/Subscriptions/Announcements.svelte',
	'src/lib/components/workspace/Models/SubscriptionPolicy.svelte',
	'src/lib/components/admin/Settings/Email.svelte',
	'src/lib/components/admin/AdminSettingsModal.svelte',
	'src/routes/(app)/model-marketplace/+page.svelte',
	'src/lib/components/models/ModelCallChart.svelte'
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
		if (!api.includes(`export const ${name}`))
			failures.push(`Missing announcement API helper ${name}`);
	}
	if (!api.includes('include_inactive'))
		failures.push('Announcement API must expose include_inactive');
}

const adminAnnouncements = read(
	'src/lib/components/admin/Settings/Subscriptions/Announcements.svelte'
);
for (const marker of [
	'deleteAdminAnnouncement',
	"toast.success('公告已永久删除。')",
	'DEFAULT_IMAGE_URL',
	'<Switch'
]) {
	if (!adminAnnouncements.includes(marker)) failures.push(`Announcement admin missing ${marker}`);
}
for (const marker of ['showInactive', '显示已停用']) {
	if (adminAnnouncements.includes(marker))
		failures.push(`Announcement admin retains removed ${marker}`);
}

const modelAccess = read('src/lib/components/admin/Settings/Subscriptions/ModelAccess.svelte');
for (const marker of ['updateAdminModelSubscriptionPolicies', 'dirty', '保存更改']) {
	if (!modelAccess.includes(marker)) failures.push(`Model access bulk save missing ${marker}`);
}
if (modelAccess.includes('updateAdminModelSubscriptionPolicy(')) {
	failures.push('Model access must not save one model at a time');
}
if ((modelAccess.match(/保存更改/g) ?? []).length !== 1) {
	failures.push('Model access must contain exactly one 保存更改 command');
}

const pricingFields = [
	'input_chatpoint_per_million',
	'output_chatpoint_per_million',
	'cache_creation_chatpoint_per_million',
	'cache_read_chatpoint_per_million'
];
for (const file of [
	'src/lib/components/admin/Settings/Subscriptions/ModelAccess.svelte',
	'src/lib/components/workspace/Models/SubscriptionPolicy.svelte',
	'src/lib/components/workspace/Models/ModelEditor.svelte'
]) {
	const text = read(file);
	for (const field of pricingFields) {
		if (!text.includes(field)) failures.push(`${file} missing ${field}`);
	}
}

const settingsModal = read('src/lib/components/chat/SettingsModal.svelte');
for (const marker of [
	"import Subscription from './Settings/Subscription.svelte'",
	"import RedeemCode from './Settings/RedeemCode.svelte'",
	"import UsageCenter from './Settings/UsageCenter.svelte'",
	"id: 'subscription'",
	"id: 'redeem_code'",
	"id: 'usage'",
	"title: 'Usage'",
	"$i18n.t('Usage')",
	'<Subscription',
	'<RedeemCode',
	'<UsageCenter'
]) {
	if (!settingsModal.includes(marker)) failures.push(`User billing settings missing ${marker}`);
}
for (const adminMarker of [
	"id: 'admin:",
	"selectedTab === 'admin:",
	'AdminGeneral',
	'AdminTabIcon'
]) {
	if (settingsModal.includes(adminMarker)) {
		failures.push(`Personal settings must not embed admin control ${adminMarker}`);
	}
}

const account = read('src/lib/components/chat/Settings/Account.svelte');
const accountSecurity = read('src/lib/components/chat/Settings/Account/AccountSecurity.svelte');
if (!account.includes('AccountSecurity') || !accountSecurity.includes('BillingAddress')) {
	failures.push('Account settings must include BillingAddress through AccountSecurity');
}

const subscriptionCenter = read('src/lib/components/chat/Settings/SubscriptionCenter.svelte');
for (const marker of ['SubscriptionUsage', 'Subscription', 'RedeemCode']) {
	if (!subscriptionCenter.includes(marker)) {
		failures.push(`Subscription center missing ${marker}`);
	}
}
const subscriptionRoute = read('src/routes/(app)/account/subscription/+page.svelte');
if (!subscriptionRoute.includes('SubscriptionCenter')) {
	failures.push('Account subscription route must mount SubscriptionCenter');
}

const userMenu = read('src/lib/components/layout/Sidebar/UserMenu.svelte');
for (const marker of ['SubscriptionQuotaRing', 'showQuota', "showSettings.set('usage')"]) {
	if (!userMenu.includes(marker)) failures.push(`UserMenu quota fallback missing ${marker}`);
}

const sidebar = read('src/lib/components/layout/Sidebar.svelte');
for (const marker of [
	"import PendingGiftEntry from './Sidebar/PendingGiftEntry.svelte'",
	"import SubscriptionQuotaRing from './Sidebar/SubscriptionQuotaRing.svelte'",
	'<PendingGiftEntry',
	'<SubscriptionQuotaRing',
	"showSettings.set('redeem_code')",
	"showSettings.set('usage')"
]) {
	if (!sidebar.includes(marker)) failures.push(`Sidebar billing entry missing ${marker}`);
}

const ring = read('src/lib/components/layout/Sidebar/SubscriptionQuotaRing.svelte');
for (const marker of [
	'用量 / Usage',
	'Plan Chatpoint',
	'Check Chatpoint',
	'refreshSubscription',
	'exhausted',
	'stroke-red'
]) {
	if (!ring.includes(marker)) failures.push(`Quota ring missing ${marker}`);
}

if (ring.includes('免费版')) failures.push('Quota ring must use Free instead of 免费版');

const chat = read('src/lib/components/chat/Chat.svelte');
if (!chat.includes("import { notifySubscriptionChanged } from '$lib/stores/subscriptions'")) {
	failures.push('Chat must import the subscription refresh notifier');
}
if ((chat.match(/void notifySubscriptionChanged\(\);/g) ?? []).length < 2) {
	failures.push('Chat must refresh subscription state at both response completion boundaries');
}

for (const file of sourceFiles(path.join(root, 'src'))) {
	const source = fs.readFileSync(file, 'utf8');
	if (
		/showSettings\.set\(\s*['"]admin:/.test(source) ||
		/showSettings\.set\(\s*\{[\s\S]{0,160}?\btab:\s*['"]admin:/.test(source)
	) {
		failures.push(
			`Admin settings state must not be written to personal settings: ${path.relative(root, file)}`
		);
	}
}

const adminSettings = read('src/lib/components/admin/Settings.svelte');
if (
	adminSettings.includes("selectedTab === 'subscriptions'") ||
	adminSettings.includes('<Subscriptions')
) {
	failures.push('Subscription operations must not remain embedded in admin settings');
}
for (const marker of [
	"import Platform from './Settings/Platform.svelte'",
	"import Email from './Settings/Email.svelte'",
	"id: 'platform'",
	"id: 'email'",
	"selectedTab === 'platform'",
	"selectedTab === 'email'",
	'<Platform',
	'<Email'
]) {
	if (!adminSettings.includes(marker)) failures.push(`Admin settings missing ${marker}`);
}

const adminLayout = read('src/routes/(app)/admin/+layout.svelte');
for (const marker of [
	'href="/admin/subscriptions"',
	'admin-mobile-section',
	'handleAdminSectionChange',
	'AdminSettingsModal',
	"showAdminSettings = 'general'"
]) {
	if (!adminLayout.includes(marker)) failures.push(`Admin navigation missing ${marker}`);
}
for (const marker of ['showSettings', 'admin:general']) {
	if (adminLayout.includes(marker))
		failures.push(`Admin layout must not use personal settings ${marker}`);
}

if (exists('src/lib/components/admin/Subscriptions/SubscriptionHome.svelte')) {
	const subscriptionHome = read('src/lib/components/admin/Subscriptions/SubscriptionHome.svelte');
	for (const route of ['plans', 'models', 'redeem-codes', 'gift-cards', 'announcements', 'usage']) {
		if (!subscriptionHome.includes(`/admin/subscriptions/${route}`)) {
			failures.push(`Subscription home missing route ${route}`);
		}
	}
}

const redeemCode = read('src/lib/components/chat/Settings/RedeemCode.svelte');
for (const marker of [
	'兑换权益',
	'{#if !giftLoading && giftCards.length > 0}',
	"gift.memo ?? '礼品卡'",
	'claimGiftCard',
	'notifySubscriptionChanged'
]) {
	if (!redeemCode.includes(marker)) failures.push(`Redeem page missing ${marker}`);
}
if (redeemCode.indexOf('兑换权益') > redeemCode.indexOf('{#if !giftLoading')) {
	failures.push('Redeem benefit card must appear before pending gift cards');
}
if (redeemCode.includes('rounded-full')) {
	failures.push('Redeem and claim actions must use rectangular buttons');
}
for (const marker of ['max-w-2xl', 'h-7', 'sm:flex-row', "gift.memo ?? '礼品卡'"]) {
	if (!redeemCode.includes(marker)) failures.push(`Redeem personal UI missing ${marker}`);
}

const personalSubscription = read('src/lib/components/chat/Settings/Subscription.svelte');
for (const marker of ['rounded-lg border', 'h-7', 'text-[13px]']) {
	if (!personalSubscription.includes(marker))
		failures.push(`Personal subscription UI missing ${marker}`);
}
if (/<button[^>]*rounded-full/.test(personalSubscription)) {
	failures.push('Personal subscription actions must use rectangular controls');
}

const personalCenter = read('src/lib/components/chat/Settings/SubscriptionCenter.svelte');
for (const marker of ['h-7', 'bg-gray-100 p-0.5', 'text-[0.6875rem]']) {
	if (!personalCenter.includes(marker)) failures.push(`Subscription center UI missing ${marker}`);
}

const billingAddress = read('src/lib/components/chat/Settings/Account/BillingAddress.svelte');
for (const marker of ['rounded-lg border', 'sm:grid-cols-2', 'h-7', '保存付款信息']) {
	if (!billingAddress.includes(marker)) failures.push(`Billing information UI missing ${marker}`);
}

const pendingGiftEntry = read('src/lib/components/layout/Sidebar/PendingGiftEntry.svelte');
for (const marker of [
	"import Gift from '$lib/components/icons/Gift.svelte'",
	'<Gift',
	'rounded-lg border',
	'w-full'
]) {
	if (!pendingGiftEntry.includes(marker)) failures.push(`Pending gift entry missing ${marker}`);
}

const adminRedeemCodes = read('src/lib/components/admin/Settings/Subscriptions/RedeemCodes.svelte');
for (const marker of [
	'自定义前缀',
	'code_template',
	'code_prefix',
	'deleteAdminRedemptionCode',
	'clearAdminRedemptionCodes',
	'code.code ?? code.code_preview'
]) {
	if (!adminRedeemCodes.includes(marker)) failures.push(`Admin redeem codes missing ${marker}`);
}

const usageLedger = read('src/lib/components/admin/Settings/Subscriptions/UsageLedger.svelte');
if (!usageLedger.includes('user?.email')) failures.push('Usage ledger must display user email');
for (const marker of [
	...pricingFields.map((field) => field.replace('_chatpoint_per_million', '_tokens')),
	'statusFilter',
	'selectedUser',
	'modelSegments',
	'conic-gradient',
	'since_registration',
	'total_item_count',
	'getAdminSubscriptionUsageOverview',
	'getAdminSubscriptionLedger',
	'exportAdminSubscriptionUsage',
	'changeRequestPage',
	'changeBalancePage'
]) {
	if (!usageLedger.includes(marker)) failures.push(`Admin usage ledger missing ${marker}`);
}
for (const marker of [
	'total_plan_cost_micros',
	'total_check_cost_micros',
	'total_unpaid_cost_micros',
	'item.plan_cost_micros',
	'item.check_cost_micros'
]) {
	if (!usageLedger.includes(marker))
		failures.push(`Admin usage ledger cost split missing ${marker}`);
}
if (usageLedger.includes('formatChatpoint(usage.total_cost_micros)')) {
	failures.push('Admin usage ledger must not label accrued cost as deducted Chatpoint');
}
if (usageLedger.includes('formatChatpoint(item.cost_micros)')) {
	failures.push('Admin usage rows must show deducted and unpaid Chatpoint separately');
}

const subscriptionStore = read('src/lib/stores/subscriptions.ts');
for (const marker of ['subscriptionLoadError', 'subscriptionLoadError.set(true)']) {
	if (!subscriptionStore.includes(marker))
		failures.push(`Subscription refresh state missing ${marker}`);
}
if (subscriptionStore.includes('getMySubscription(authToken).catch(() => null)')) {
	failures.push('Subscription refresh failures must preserve the last successful snapshot');
}

const activityUsage = read('src/lib/components/chat/Settings/Usage.svelte');
for (const marker of ['getUserUsage', "i18n.t('Activity')", 'Activity insights']) {
	if (!activityUsage.includes(marker)) failures.push(`Activity analytics missing ${marker}`);
}
for (const billingMarker of ['getMySubscriptionUsage', '$lib/apis/subscriptions', 'client_ip']) {
	if (activityUsage.includes(billingMarker)) {
		failures.push(`Activity analytics must not contain billing marker ${billingMarker}`);
	}
}

const usageCenter = read('src/lib/components/chat/Settings/UsageCenter.svelte');
for (const marker of [
	"let view: UsageView = 'billing'",
	"import ActivityUsage from './Usage.svelte'",
	"import SubscriptionUsage from './SubscriptionUsage.svelte'",
	"view === 'billing'",
	'<SubscriptionUsage',
	'<ActivityUsage'
]) {
	if (!usageCenter.includes(marker)) failures.push(`Combined usage entry missing ${marker}`);
}

const subscriptionUsage = read('src/lib/components/chat/Settings/SubscriptionUsage.svelte');
for (const marker of [
	'getMySubscriptionUsage',
	'total_input_tokens',
	'total_output_tokens',
	'total_cache_creation_tokens',
	'total_cache_read_tokens',
	'total_plan_cost_micros',
	'total_check_cost_micros',
	'total_request_count',
	'plan_cost_micros',
	'check_cost_micros',
	'unpaid_cost_micros',
	'first_token_latency_ms',
	'total_duration_ms',
	'plan_delta_micros'
]) {
	if (!subscriptionUsage.includes(marker)) {
		failures.push(`Subscription billing usage missing ${marker}`);
	}
}
if (subscriptionUsage.includes('client_ip')) {
	failures.push('User subscription usage must not reference client_ip');
}

for (const file of [
	'backend/open_webui/routers/analytics.py',
	'backend/open_webui/routers/chats.py'
]) {
	const text = read(file);
	for (const billingMarker of [
		'models.subscriptions',
		'SubscriptionUsages',
		'UserSubscriptions',
		'debit_balances'
	]) {
		if (text.includes(billingMarker)) {
			failures.push(
				`Official activity analytics must not depend on billing marker ${billingMarker} in ${file}`
			);
		}
	}
}

const billingUtility = read('backend/open_webui/utils/subscriptions.py');
for (const marker of [
	'billing_idempotency_key',
	'IntegrityError',
	'idempotency_key=idempotency_key'
]) {
	if (!billingUtility.includes(marker)) failures.push(`Billing idempotency missing ${marker}`);
}
const billingModel = read('backend/open_webui/models/subscriptions.py');
if (
	!billingModel.includes(
		"Index('uq_subscription_usage_idempotency_key', 'idempotency_key', unique=True)"
	)
) {
	failures.push('Billing usage must enforce a database-unique idempotency key');
}
if (!exists('backend/open_webui/migrations/versions/e4f5a6b7c8d9_add_billing_idempotency_key.py')) {
	failures.push('Billing idempotency migration is missing');
}

const configSource = read('backend/open_webui/config.py');
if (
	!configSource.includes(
		"ENABLE_DIRECT_CONNECTIONS = os.getenv('ENABLE_DIRECT_CONNECTIONS', 'False')"
	)
) {
	failures.push('Direct Connections must remain disabled by default for hosted billing');
}

for (const file of [
	'backend/open_webui/utils/settings_security.py',
	'src/lib/utils/direct-connections.ts'
]) {
	if (!exists(file)) failures.push(`Direct Connections secret isolation missing ${file}`);
}
if (exists('backend/open_webui/utils/settings_security.py')) {
	const settingsSecurity = read('backend/open_webui/utils/settings_security.py');
	for (const marker of ['sanitize_user_settings', "ui.pop('directConnections', None)"]) {
		if (!settingsSecurity.includes(marker)) {
			failures.push(`Server settings sanitizer missing ${marker}`);
		}
	}
}
if (exists('src/lib/utils/direct-connections.ts')) {
	const directConnections = read('src/lib/utils/direct-connections.ts');
	for (const marker of [
		'artichat.direct-connections.v1',
		'prepareUserSettingsForServer',
		'saveDirectConnections',
		'const { directConnections, ...serverUi }'
	]) {
		if (!directConnections.includes(marker)) {
			failures.push(`Browser-only Direct Connections storage missing ${marker}`);
		}
	}
}
const usersRouter = read('backend/open_webui/routers/users.py');
if ((usersRouter.match(/sanitize_user_settings\(/g) ?? []).length < 2) {
	failures.push('User settings GET and UPDATE must both sanitize Direct Connections secrets');
}
const usersApi = read('src/lib/apis/users/index.ts');
if (!usersApi.includes('JSON.stringify(prepareUserSettingsForServer(token, settings))')) {
	failures.push('User settings API must strip Direct Connections before POST');
}

const mainSource = read('backend/open_webui/main.py');
for (const marker of ["Config.get('direct.enable')", "metadata['billing_mode'] = 'byok'"]) {
	if (!mainSource.includes(marker)) {
		failures.push(`Direct Connections billing isolation missing ${marker}`);
	}
}
if (!mainSource.includes('len(message_ids) > 8')) {
	failures.push('Chat fanout must remain capped at eight model targets');
}

const inferenceAccess = read('backend/open_webui/utils/inference_access.py');
for (const marker of [
	'RAW_PROVIDER_PREFIXES',
	"getattr(user, 'role', None) != 'admin'",
	'HTTP_403_FORBIDDEN'
]) {
	if (!inferenceAccess.includes(marker))
		failures.push(`Raw provider access gate missing ${marker}`);
}
for (const [file, expectedCalls] of [
	['backend/open_webui/routers/openai.py', 4],
	['backend/open_webui/routers/ollama.py', 6]
]) {
	const callCount = (
		read(file).match(/assert_raw_provider_generation_access\(request, user\)/g) ?? []
	).length;
	if (callCount !== expectedCalls) {
		failures.push(`${file} must gate ${expectedCalls} raw generation handlers, found ${callCount}`);
	}
}
if (!mainSource.includes("user.role == 'admin' and is_anthropic_messages_passthrough")) {
	failures.push('Native Anthropic passthrough must remain admin-only');
}

const hostedInference = read('backend/open_webui/utils/hosted_inference.py');
for (const marker of [
	'prepare_hosted_inference',
	'generate_billed_chat_completion',
	'HOSTED_POLICY_MODEL_ID',
	'RESERVATION_ID',
	'reserve_chatpoints',
	'release_hosted_inference_reservation',
	'allow_partial_reservation=True',
	'Hosted inference billing context is missing',
	"'billing_scope': 'internal_inference'"
]) {
	if (!hostedInference.includes(marker)) {
		failures.push(`Hosted inference broker missing ${marker}`);
	}
}
const middlewareSource = read('backend/open_webui/utils/middleware.py');
for (const marker of [
	"reservation_id = metadata.get('_artichat_chatpoint_reservation_id')",
	'allow_partial_reservation=True',
	'release_subscription_reservation_once'
]) {
	if (!middlewareSource.includes(marker)) {
		failures.push(`Chatpoint settlement lifecycle missing ${marker}`);
	}
}
for (const marker of [
	'release_hosted_inference_reservation',
	'release_hosted_inference_reservation_shielded',
	"metadata = form_data['metadata']",
	'reservation_cleanup_loop',
	'release_expired_chatpoint_reservations'
]) {
	if (!mainSource.includes(marker))
		failures.push(`Main chat reservation lifecycle missing ${marker}`);
}
const chatSource = read('backend/open_webui/utils/chat.py');
for (const marker of [
	'_artichat_chatpoint_reservation_id',
	'form_metadata.clear()',
	'form_metadata.update(merged_metadata)'
]) {
	if (!chatSource.includes(marker))
		failures.push(`Chat metadata reservation propagation missing ${marker}`);
}
const tasksRouter = read('backend/open_webui/routers/tasks.py');
if (tasksRouter.includes('from open_webui.utils.chat import generate_chat_completion')) {
	failures.push('Task completions must not import the unbilled low-level chat generator');
}
if ((tasksRouter.match(/generate_billed_chat_completion\(/g) ?? []).length !== 8) {
	failures.push('All eight task completion routes must use the hosted inference broker');
}
for (const file of [
	'backend/open_webui/utils/context_compaction.py',
	'backend/open_webui/utils/memory.py'
]) {
	if (!read(file).includes('generate_billed_chat_completion')) {
		failures.push(`${file} must use the hosted inference broker`);
	}
}
if (!tasksRouter.includes('Query generation type must be web_search or retrieval.')) {
	failures.push('Query generation must reject unknown task types');
}

const announcementModal = read('src/lib/components/AnnouncementModal.svelte');
for (const marker of [
	'getActiveAnnouncements',
	'sessionStorage',
	'markAnnouncementViewed',
	'current.summary',
	'current.image_url',
	'current.view_button_label',
	'current.close_button_label',
	'closeOnBackdrop={false}',
	'closeOnEscape={false}',
	'!rounded-[18px]',
	'!border-0',
	'announcement-expanded'
]) {
	if (!announcementModal.includes(marker)) failures.push(`Announcement modal missing ${marker}`);
}

const appLayout = read('src/routes/(app)/+layout.svelte');
if (
	!appLayout.includes("import AnnouncementModal from '$lib/components/AnnouncementModal.svelte'") ||
	!appLayout.includes('<AnnouncementModal')
) {
	failures.push('App layout must mount AnnouncementModal');
}

const announcementAdmin = read(
	'src/lib/components/admin/Settings/Subscriptions/Announcements.svelte'
);
for (const marker of [
	'form.summary',
	'form.image_url',
	'form.view_button_label',
	'form.close_button_label',
	'row.summary',
	'row.image_url',
	'draft.view_button_label',
	'draft.close_button_label',
	'封面图片地址',
	'展开内容'
]) {
	if (!announcementAdmin.includes(marker)) failures.push(`Announcement admin missing ${marker}`);
}

const announcementModel = read('backend/open_webui/models/announcements.py');
const announcementRouter = read('backend/open_webui/routers/announcements.py');
const announcementApi = read('src/lib/apis/announcements/index.ts');
const announcementMigration = read(
	'backend/open_webui/migrations/versions/0a1b2c3d4e5f_add_announcement_presentation_fields.py'
);
for (const field of ['summary', 'image_url', 'view_button_label', 'close_button_label']) {
	for (const [label, text] of [
		['model', announcementModel],
		['router', announcementRouter],
		['frontend API', announcementApi],
		['migration', announcementMigration]
	]) {
		if (!text.includes(field)) failures.push(`Announcement ${label} missing ${field}`);
	}
}

const modelEditor = read('src/lib/components/workspace/Models/ModelEditor.svelte');
if (!modelEditor.includes('SubscriptionPolicy'))
	failures.push('ModelEditor must include SubscriptionPolicy');
for (const marker of ['meta.marketplace', '展示在模型广场', 'long_description']) {
	if (!modelEditor.includes(marker)) failures.push(`ModelEditor marketplace missing ${marker}`);
}

const modelMarketplace = read('src/routes/(app)/model-marketplace/+page.svelte');
for (const marker of [
	'getModelMarketplace',
	'model.is_active',
	'model.allowed_tiers',
	'model.pricing',
	'ModelCallChart'
]) {
	if (!modelMarketplace.includes(marker)) failures.push(`Model marketplace missing ${marker}`);
}

const emailSettings = read('src/lib/components/admin/Settings/Email.svelte');
for (const marker of [
	'RegistrationSettings',
	'启用邮箱功能',
	'EmailSettings',
	'EmailTemplates',
	'EmailDeliveries'
]) {
	if (!emailSettings.includes(marker))
		failures.push(`Consolidated email settings missing ${marker}`);
}

if (adminLayout.includes('/admin/registration') || adminLayout.includes('/admin/email')) {
	failures.push('Registration and email must not remain top-level admin navigation items');
}

for (const marker of ['/model-marketplace', 'customSidebarButtons', 'SidebarLinkIcon']) {
	if (!sidebar.includes(marker)) failures.push(`Sidebar extensions missing ${marker}`);
}

const editUser = read('src/lib/components/admin/Users/UserList/EditUserModal.svelte');
for (const marker of [
	'updateAdminUserSubscription',
	'plan_chatpoint',
	'check_chatpoint',
	'expires_at_input'
]) {
	if (!editUser.includes(marker))
		failures.push(`EditUserModal subscription merge missing ${marker}`);
}

const userList = read('src/lib/components/admin/Users/UserList.svelte');
for (const marker of ['user.subscription?.display_name', 'user.subscription?.expires_at']) {
	if (!userList.includes(marker)) failures.push(`UserList subscription summary missing ${marker}`);
}

if (exists('src/routes/(app)/admin/subscriptions/users/+page.svelte')) {
	failures.push('Standalone admin user subscriptions route must be removed');
}
if (exists('src/lib/components/admin/Settings/Subscriptions/UserSubscriptions.svelte')) {
	failures.push('Standalone UserSubscriptions component must be removed');
}
if (
	read('src/lib/components/admin/Subscriptions/SubscriptionHome.svelte').includes(
		'/admin/subscriptions/users'
	)
) {
	failures.push('Subscription home must not link to standalone user subscriptions');
}

if (failures.length > 0) {
	for (const failure of failures) console.error(failure);
	process.exit(1);
}

console.log('Subscription static guard passed.');
