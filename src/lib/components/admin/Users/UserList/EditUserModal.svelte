<script lang="ts">
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import { createEventDispatcher } from 'svelte';
	import { onMount, getContext } from 'svelte';

	import { goto } from '$app/navigation';

	import { updateUserById, getUserGroupsById } from '$lib/apis/users';
	import { updateAdminUserSubscription } from '$lib/apis/subscriptions';

	import Modal from '$lib/components/common/Modal.svelte';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	import XMark from '$lib/components/icons/XMark.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import UserProfileImage from '$lib/components/chat/Settings/Account/UserProfileImage.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();
	dayjs.extend(localizedFormat);

	export let show = false;
	export let selectedUser;
	export let sessionUser;

	$: if (show) {
		init();
	}

	const init = () => {
		if (selectedUser) {
			_user = { ...selectedUser };
			_user.password = '';
			const subscription = selectedUser.subscription ?? {};
			_subscription = {
				tier: subscription.tier ?? 'free',
				status: subscription.status ?? 'free',
				plan_chatpoint: `${(subscription.plan_balance_micros ?? 0) / 1_000_000}`,
				check_chatpoint: `${(subscription.check_balance_micros ?? 0) / 1_000_000}`,
				expires_at_input: toDateTimeLocal(subscription.expires_at),
				notes: subscription.notes ?? ''
			};
			loadUserGroups();
		}
	};

	let _user = {
		profile_image_url: '',
		role: 'pending',
		name: '',
		email: '',
		password: ''
	};

	let userGroups: any[] | null = null;
	let _subscription = {
		tier: 'free',
		status: 'free',
		plan_chatpoint: '0',
		check_chatpoint: '0',
		expires_at_input: '',
		notes: ''
	};

	const toDateTimeLocal = (value?: number | null) => {
		if (!value) return '';
		const date = new Date(value * 1000);
		date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
		return date.toISOString().slice(0, 16);
	};

	const fromDateTimeLocal = (value: string) =>
		value ? Math.floor(new Date(value).getTime() / 1000) : null;

	const submitHandler = async () => {
		const res = await updateUserById(localStorage.token, selectedUser.id, _user).catch((error) => {
			toast.error(`${error}`);
		});

		if (!res) return;

		const subscription = await updateAdminUserSubscription(localStorage.token, selectedUser.id, {
			tier: _subscription.tier,
			status: _subscription.status,
			plan_chatpoint: _subscription.plan_chatpoint,
			check_chatpoint: _subscription.check_chatpoint,
			expires_at: fromDateTimeLocal(_subscription.expires_at_input),
			notes: _subscription.notes || null
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (!subscription) return;
		dispatch('save');
		show = false;
	};

	const loadUserGroups = async () => {
		if (!selectedUser?.id) return;
		userGroups = null;

		userGroups = await getUserGroupsById(localStorage.token, selectedUser.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
	};
</script>

<Modal size="sm" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class=" text-lg font-medium self-center">{$i18n.t('Edit User')}</div>
			<button
				class="self-center"
				aria-label={$i18n.t('Close')}
				on:click={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<form
					class="flex flex-col w-full"
					on:submit|preventDefault={() => {
						submitHandler();
					}}
				>
					<div class=" px-5 pt-3 pb-5 w-full">
						<div class="flex self-center w-full">
							<div class=" self-start h-full mr-6">
								<UserProfileImage
									imageClassName="size-14"
									bind:profileImageUrl={_user.profile_image_url}
									user={_user}
								/>
							</div>

							<div class=" flex-1 min-w-0">
								<div class="overflow-hidden w-ful mb-2">
									<div class=" self-center capitalize font-medium truncate">
										{selectedUser.name}
									</div>

									<div class="text-xs text-gray-500">
										{$i18n.t('Created at')}
										{dayjs(selectedUser.created_at * 1000).format('LL')}
									</div>

									<div class="mt-1 text-xs text-gray-500">
										<span>用户 ID：</span>
										<span
											class="select-all break-all font-mono text-[11px] text-gray-700 dark:text-gray-300"
										>
											{selectedUser.id}
										</span>
									</div>
								</div>

								<div class=" flex flex-col space-y-1.5">
									{#if (userGroups ?? []).length > 0}
										<div class="flex flex-col w-full text-sm">
											<div class="mb-1 text-xs text-gray-500">{$i18n.t('User Groups')}</div>

											<div class="flex flex-wrap gap-1 my-0.5 -mx-1">
												{#each userGroups as userGroup}
													<span
														class="px-1.5 py-0.5 rounded-xl bg-gray-100 dark:bg-gray-850 text-xs"
													>
														<a
															href={'/admin/users/groups?id=' + userGroup.id}
															on:click|preventDefault={() =>
																goto('/admin/users/groups?id=' + userGroup.id)}
														>
															{userGroup.name}
														</a>
													</span>
												{/each}
											</div>
										</div>
									{/if}

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Role')}</div>

										<div class="flex-1">
											<select
												class="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
												bind:value={_user.role}
												aria-label={$i18n.t('Role')}
												disabled={_user.id == sessionUser.id}
												required
											>
												<option value="admin">{$i18n.t('Admin')}</option>
												<option value="user">{$i18n.t('User')}</option>
												<option value="pending">{$i18n.t('Pending')}</option>
											</select>
										</div>
									</div>

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Name')}</div>

										<div class="flex-1">
											<input
												class="w-full text-sm bg-transparent outline-hidden"
												type="text"
												bind:value={_user.name}
												aria-label={$i18n.t('Name')}
												placeholder={$i18n.t('Enter Your Name')}
												autocomplete="off"
												required
											/>
										</div>
									</div>

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Email')}</div>

										<div class="flex-1">
											<input
												class="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
												type="email"
												bind:value={_user.email}
												aria-label={$i18n.t('Email')}
												placeholder={$i18n.t('Enter Your Email')}
												autocomplete="off"
												required
											/>
										</div>
									</div>

									{#if _user?.oauth}
										<div class="flex flex-col w-full">
											<div class=" mb-1 text-xs text-gray-500">{$i18n.t('OAuth ID')}</div>

											<div class="flex-1 text-sm break-all mb-1 flex flex-col space-y-1">
												{#each Object.keys(_user.oauth) as key}
													<div>
														<span class="text-gray-500">{key}</span>
														<span class="">{_user.oauth[key]?.sub}</span>
													</div>
												{/each}
											</div>
										</div>
									{/if}

									<div class="flex flex-col w-full">
										<div class=" mb-1 text-xs text-gray-500">{$i18n.t('New Password')}</div>

										<div class="flex-1">
											<SensitiveInput
												class="w-full text-sm bg-transparent outline-hidden"
												type="password"
												aria-label={$i18n.t('New Password')}
												placeholder={$i18n.t('Enter New Password')}
												bind:value={_user.password}
												autocomplete="new-password"
												required={false}
											/>
										</div>
									</div>
								</div>
							</div>
						</div>

						<div class="mt-4 border-t border-gray-100 pt-4 dark:border-gray-850">
							<div class="mb-2 text-sm font-medium">订阅与额度</div>
							<div class="grid grid-cols-2 gap-2">
								<label class="flex flex-col gap-1"
									><span class="text-xs text-gray-500">订阅</span><select
										class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 text-sm dark:border-gray-850"
										bind:value={_subscription.tier}
										><option value="free">Free</option><option value="plus">Plus</option><option
											value="chatpower">ChatPower</option
										></select
									></label
								>
								<label class="flex flex-col gap-1"
									><span class="text-xs text-gray-500">状态</span><select
										class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 text-sm dark:border-gray-850"
										bind:value={_subscription.status}
										><option value="free">Free</option><option value="active">有效</option><option
											value="expired">已过期</option
										><option value="inactive">未启用</option></select
									></label
								>
								<label class="col-span-2 flex flex-col gap-1"
									><span class="text-xs text-gray-500">到期时间</span><input
										type="datetime-local"
										class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 text-sm dark:border-gray-850"
										bind:value={_subscription.expires_at_input}
									/></label
								>
								<label class="flex flex-col gap-1"
									><span class="text-xs text-gray-500">周期 Chatpoint</span><input
										type="number"
										step="any"
										class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 text-sm dark:border-gray-850"
										bind:value={_subscription.plan_chatpoint}
									/></label
								>
								<label class="flex flex-col gap-1"
									><span class="text-xs text-gray-500">充值 Chatpoint</span><input
										type="number"
										step="any"
										class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 text-sm dark:border-gray-850"
										bind:value={_subscription.check_chatpoint}
									/></label
								>
								<label class="col-span-2 flex flex-col gap-1"
									><span class="text-xs text-gray-500">管理员备注</span><input
										class="rounded-lg border border-gray-100 bg-transparent px-2 py-1 text-sm dark:border-gray-850"
										bind:value={_subscription.notes}
									/></label
								>
							</div>
						</div>

						<div class="flex justify-end pt-3 text-sm font-medium">
							<button
								class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full flex flex-row space-x-1 items-center"
								type="submit"
							>
								{$i18n.t('Save')}
							</button>
						</div>
					</div>
				</form>
			</div>
		</div>
	</div>
</Modal>

<style>
	input::-webkit-outer-spin-button,
	input::-webkit-inner-spin-button {
		/* display: none; <- Crashes Chrome on hover */
		-webkit-appearance: none;
		margin: 0; /* <-- Apparently some margin are still there even though it's hidden */
	}

	.tabs::-webkit-scrollbar {
		display: none; /* for Chrome, Safari and Opera */
	}

	.tabs {
		-ms-overflow-style: none; /* IE and Edge */
		scrollbar-width: none; /* Firefox */
	}

	input[type='number'] {
		-moz-appearance: textfield; /* Firefox */
	}
</style>
