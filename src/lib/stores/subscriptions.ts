import { writable } from 'svelte/store';

import { getMySubscription, type UserSubscription } from '$lib/apis/subscriptions';

export const subscription = writable<UserSubscription | null>(null);
export const subscriptionLoadError = writable(false);
export const subscriptionRefreshTick = writable(0);

export const refreshSubscription = async (token?: string) => {
	const authToken =
		token ?? (typeof localStorage !== 'undefined' ? (localStorage.getItem('token') ?? '') : '');

	if (!authToken) {
		subscription.set(null);
		subscriptionLoadError.set(false);
		return null;
	}

	try {
		const data = await getMySubscription(authToken);
		subscription.set(data);
		subscriptionLoadError.set(false);
		return data;
	} catch {
		subscriptionLoadError.set(true);
		return null;
	}
};

export const notifySubscriptionChanged = async () => {
	subscriptionRefreshTick.update((value) => value + 1);
	return refreshSubscription();
};
