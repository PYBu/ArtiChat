import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';
import type { OperationStatusConfig } from '$lib/utils/operationStatus';

export const getOperationStatusConfig = async (token: string) =>
	apiJsonFetch<OperationStatusConfig>(`${WEBUI_API_BASE_URL}/configs/operation-status`, token);

export const updateOperationStatusConfig = async (token: string, config: OperationStatusConfig) =>
	apiJsonFetch<OperationStatusConfig>(`${WEBUI_API_BASE_URL}/configs/operation-status`, token, {
		method: 'POST',
		body: JSON.stringify(config)
	});
