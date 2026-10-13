import fs from 'node:fs';

const read = (file) => fs.readFileSync(file, 'utf8');
const users = read('backend/open_webui/models/users.py');
const auths = read('backend/open_webui/routers/auths.py');
const middleware = read('backend/open_webui/utils/middleware.py');
const qdrant = read('backend/open_webui/retrieval/vector/dbs/qdrant.py');
const qdrantMulti = read('backend/open_webui/retrieval/vector/dbs/qdrant_multitenancy.py');
const retrieval = read('backend/open_webui/retrieval/utils.py');
const vector = read('backend/open_webui/retrieval/vector/utils.py');
const web = read('backend/open_webui/retrieval/web/utils.py');
const misc = read('backend/open_webui/utils/misc.py');
const config = read('backend/open_webui/config.py');
const folders = read('backend/open_webui/routers/folders.py');
const folderModel = read('backend/open_webui/models/folders.py');
const channelsModel = read('backend/open_webui/models/channels.py');
const messagesModel = read('backend/open_webui/models/messages.py');
const channelsRouter = read('backend/open_webui/routers/channels.py');
const env = read('backend/open_webui/env.py');
const tools = read('backend/open_webui/utils/tools.py');
const builtin = read('backend/open_webui/tools/builtin.py');
const preview = read('src/lib/components/chat/FileNav/PortPreview.svelte');

const checks = [
	[users.includes("User.oauth[provider]['sub'].as_string()"), 'OAuth subject uses exact JSON path matching'],
	[users.includes("User.scim[provider]['external_id'].as_string()"), 'SCIM external ID uses exact JSON path matching'],
	[!users.includes('.oauth.contains(') && !users.includes('.scim.contains('), 'OAuth/SCIM broad JSON containment is absent'],
	[auths.includes('oauth_manager.get_user_role(user, user_data)'), 'Token exchange applies OAuth role policy'],
	[middleware.includes("'features.memories'") && middleware.includes('add_memory_context'), 'Legacy memory context checks permission'],
	[qdrant.includes('scroll_filter=_metadata_query_filter(filter)'), 'Qdrant query uses the shared filter contract'],
	[qdrant.includes('models.Filter(must=conditions)'), 'Qdrant vector search combines filters with AND'],
  [qdrantMulti.includes('metadata_conditions') && qdrantMulti.includes('iter_filter_conditions(filter)'), 'Multitenant Qdrant search applies metadata filters'],
  [retrieval.includes('response.iter_content') && retrieval.includes('FILE_TOO_LARGE'), 'Binary web downloads are streamed and bounded'],
  [vector.includes('RAG_METADATA_MAX_VALUE_CHARS') && vector.includes("'documents'") && vector.includes("'styles'"), 'Extracted metadata fields are bounded'],
  [web.includes('class _SSRFSafeConnector') && web.includes('_resolve_host') && web.includes('is_host_blocked'), 'Web fetch validates connect-time addresses and filter targets'],
  [misc.includes('def is_host_blocked') && misc.includes('ipaddress.ip_network'), 'Web filter list supports CIDR ranges'],
  [config.includes("'!168.63.129.16'") && config.includes("'!ff00::/8'"), 'Reserved web-fetch ranges are blocked by default'],
  [folders.includes('validate_folder_parent_id') && folders.includes('own subtree'), 'Folder moves reject parent cycles'],
  [folderModel.includes('collect_folder_subtree_ids') && folderModel.includes('select(Folder.id, Folder.parent_id)'), 'Folder subtree lookup is batched'],
  [channelsModel.includes('get_members_by_channel_ids') && messagesModel.includes('get_last_message_at_by_channel_ids') && messagesModel.includes('get_unread_message_counts_by_channel_ids'), 'Channel list batch model queries exist'],
  [channelsRouter.includes('get_last_message_at_by_channel_ids') && channelsRouter.includes('get_members_by_channel_ids'), 'Channel list avoids per-channel reads'],
  [env.includes('AIOHTTP_CLIENT_MAX_CONTENT_LENGTH_TOOL_SERVER_DATA'), 'Tool server response limit is configurable'],
  [tools.includes('_read_tool_server_response_bounded') && tools.includes('iter_chunked'), 'Tool server specs are read with a byte bound'],
  [tools.includes("headers.update(bearer_auth_header(connection.get('key', '')))") && tools.includes('bearer_auth_header(token) or None') && tools.includes("connection.get('forward_cookies', False)"), 'Tool server bearer headers are normalized and cookie forwarding is opt-in'],
  [builtin.includes('file and await _has_read_access_to_file(') && builtin.includes('__model_knowledge__'), 'Attached file knowledge retrieval checks read access'],
  [web.includes('urllib.parse.urljoin') && web.includes('validate_url(url)') && web.includes('allow_redirects=False'), 'Playwright redirect targets are revalidated'],
	[preview.includes('iframeSandboxAllowSameOrigin') && !/sandbox="[^\n]*allow-same-origin[^\n]*"/.test(preview), 'Port preview same-origin is opt-in'],
	[preview.includes('allow-popups') && preview.includes('allow-modals'), 'Port preview retains popup/modal capabilities'],
];

for (const [passed, message] of checks) {
	if (!passed) throw new Error(`Security backport check failed: ${message}`);
}

console.log(`Security backport guard passed (${checks.length} checks).`);
