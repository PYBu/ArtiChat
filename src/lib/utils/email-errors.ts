const messages: Record<string, string> = {
	EMAIL_CODE_RESEND_COOLDOWN: '请等待 60 秒后重新发送验证码。',
	EMAIL_CODE_EMAIL_RATE_LIMIT: '该邮箱请求过于频繁，请一小时后重试。',
	EMAIL_CODE_IP_RATE_LIMIT: '当前网络请求过于频繁，请一小时后重试。',
	EMAIL_CODE_EXPIRED: '验证码已过期，请重新发送。',
	EMAIL_CODE_ALREADY_USED: '验证码已使用，请重新发送。',
	EMAIL_CODE_ATTEMPTS_EXCEEDED: '验证码错误次数过多，请重新发送。',
	EMAIL_CODE_INVALID: '验证码不正确，请检查后重试。',
	EMAIL_VERIFICATION_TICKET_EXPIRED: '验证已过期，请重新发送验证码。',
	SENSITIVE_ACTION_GRANT_EXPIRED: '安全验证已过期，请重新发送验证码。',
	SENSITIVE_ACTION_GRANT_USED: '安全验证已使用，请重新发送验证码。',
	EMAIL_DELIVERY_DISABLED: '邮件服务尚未配置，请联系管理员。',
	EMAIL_DELIVERY_FAILED: '邮件发送失败，请稍后重试或联系管理员。',
	REGISTRATION_VERIFICATION_DISABLED: '注册邮箱验证当前未开启。',
	EMAIL_CODE_LOGIN_DISABLED: '邮箱验证码登录当前未开启。'
};

export const emailErrorMessage = (error: unknown) => {
	const code = String(error);
	return messages[code] ?? code;
};
