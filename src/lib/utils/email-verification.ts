export const normalizeEmailVerificationCode = (value: string) =>
	value.normalize('NFKC').replace(/\D/g, '').slice(0, 6);

export const isEmailVerificationCodeComplete = (value: string) =>
	/^\d{6}$/.test(normalizeEmailVerificationCode(value));
