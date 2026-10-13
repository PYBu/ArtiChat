export type MediaFile = {
	type?: string;
	content_type?: string;
	url?: string;
	id?: string;
};

export type MediaGeneration = {
	tool_call_id: string;
	media_type?: 'image' | 'video';
	operation?: 'generate' | 'edit';
	phase?: 'start' | 'success' | 'failure';
	files?: MediaFile[];
};

export const resolveMediaGenerations = (
	generations: MediaGeneration[] | undefined,
	messageFiles: MediaFile[] | undefined
): MediaGeneration[] => {
	const items = Array.isArray(generations) ? generations : [];
	const files = Array.isArray(messageFiles)
		? messageFiles.filter((file) => {
				const contentType = file?.content_type ?? '';
				return (
					file?.type === 'image' ||
					file?.type === 'video' ||
					contentType.startsWith('image/') ||
					contentType.startsWith('video/')
				);
			})
		: [];
	const pending = items.filter(
		(generation) =>
			generation?.phase !== 'failure' &&
			!(generation?.files ?? []).some((file) => file?.id || file?.url)
	);

	if (files.length === 0 || pending.length !== 1) return items;

	const pendingGeneration = pending[0];
	const claimedFileKeys = new Set(
		items.flatMap((generation) =>
			(generation.files ?? []).flatMap((file) => [file?.id, file?.url].filter(Boolean))
		)
	);
	const matchingFiles = files.filter((file) => {
		if (claimedFileKeys.has(file?.id) || claimedFileKeys.has(file?.url)) return false;
		const contentType = file?.content_type ?? '';
		const isVideo = file?.type === 'video' || contentType.startsWith('video/');
		return pendingGeneration.media_type === 'video' ? isVideo : !isVideo;
	});

	if (matchingFiles.length === 0) return items;

	return items.map((generation) =>
		generation === pendingGeneration
			? { ...generation, phase: 'success', files: matchingFiles }
			: generation
	);
};
