import type { UpdateStage, UpdateState } from '$lib/apis/updates';

const activeStages = new Set<UpdateStage>([
	'queued',
	'preparing',
	'pulling',
	'backing_up',
	'restarting',
	'verifying'
]);

const labels: Record<UpdateStage, string> = {
	idle: '尚未开始更新',
	queued: '等待部署任务',
	preparing: '正在准备更新',
	pulling: '正在下载新镜像',
	backing_up: '正在备份数据',
	restarting: '正在重启 ArtiChat',
	verifying: '正在验证新版本',
	completed: '更新完成',
	failed: '更新失败',
	rolled_back: '更新失败，已回滚'
};

export const isActiveUpdateStage = (stage: UpdateStage) => activeStages.has(stage);

export const shouldPollUpdate = (state?: Pick<UpdateState, 'stage' | 'active'> | null) =>
	Boolean(state?.active || (state && isActiveUpdateStage(state.stage)));

export const updateStageLabel = (stage: UpdateStage) => labels[stage] ?? labels.failed;
