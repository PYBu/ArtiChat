import { WEBUI_API_BASE_URL } from '$lib/constants';
import { apiJsonFetch } from '$lib/apis/base';

export type AuthSession = Record<string, unknown> & { token?: string };

export const userEmailCodeSignIn = async (email: string, verificationToken: string) =>
	apiJsonFetch<AuthSession>(`${WEBUI_API_BASE_URL}/auths/signin/email-code`, null, {
		method: 'POST',
		credentials: 'include',
		body: JSON.stringify({ email, verification_token: verificationToken })
	});

export const userSignUpWithVerification = async (
	name: string,
	email: string,
	password: string,
	profileImageUrl: string,
	verificationToken: string | null
) =>
	apiJsonFetch<AuthSession>(`${WEBUI_API_BASE_URL}/auths/signup`, null, {
		method: 'POST',
		credentials: 'include',
		body: JSON.stringify({
			name,
			email,
			password,
			profile_image_url: profileImageUrl,
			verification_token: verificationToken
		})
	});

export const updateUserPasswordWithVerification = async (
	token: string,
	password: string,
	newPassword: string,
	verificationToken: string | null
) =>
	apiJsonFetch<Record<string, unknown>>(`${WEBUI_API_BASE_URL}/auths/update/password`, token, {
		method: 'POST',
		body: JSON.stringify({
			password,
			new_password: newPassword,
			verification_token: verificationToken
		})
	});

export const updateUserEmail = async (
	token: string,
	email: string,
	verificationToken: string | null
) =>
	apiJsonFetch<Record<string, unknown>>(`${WEBUI_API_BASE_URL}/auths/update/email`, token, {
		method: 'POST',
		body: JSON.stringify({ email, verification_token: verificationToken })
	});
