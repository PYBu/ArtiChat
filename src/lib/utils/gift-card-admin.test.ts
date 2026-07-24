import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

describe('gift card recipient selection', () => {
	it('searches users by name or email and submits stable user ids', () => {
		const giftCards = readFileSync(
			resolve('src/lib/components/admin/Settings/Subscriptions/GiftCards.svelte'),
			'utf8'
		);

		expect(giftCards).toContain("import { searchUsers } from '$lib/apis/users'");
		expect(giftCards).toContain('placeholder="输入姓名或邮箱搜索"');
		expect(giftCards).toContain('selectedUsers.map((user) => user.id)');
		expect(giftCards).not.toContain('user_ids_text');
	});

	it('shows the stable id in the edit-user modal', () => {
		const editUser = readFileSync(
			resolve('src/lib/components/admin/Users/UserList/EditUserModal.svelte'),
			'utf8'
		);

		expect(editUser).toContain('用户 ID：');
		expect(editUser).toContain('{selectedUser.id}');
	});
});
