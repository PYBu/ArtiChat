import { describe, expect, it } from 'vitest';

import { buildOutputDisplayItems } from './structuredOutput';

describe('structured output display filtering', () => {
	it('does not expose memory maintenance calls or their results', () => {
		const items = buildOutputDisplayItems([
			{
				type: 'function_call',
				call_id: 'memory-1',
				name: 'add_memory',
				status: 'completed',
				arguments: '{"content":"User prefers concise replies"}'
			},
			{
				type: 'function_call_output',
				call_id: 'memory-1',
				output: [{ type: 'output_text', text: '{"status":"success"}' }]
			},
			{
				type: 'message',
				id: 'message-1',
				content: [{ type: 'output_text', text: 'I remembered it.' }]
			}
		]);

		expect(items).toEqual([{ type: 'message', id: 'message-1', text: 'I remembered it.' }]);
	});

	it('keeps ordinary function calls visible', () => {
		const items = buildOutputDisplayItems([
			{
				type: 'function_call',
				call_id: 'search-1',
				name: 'search_web',
				status: 'completed'
			},
			{
				type: 'function_call_output',
				call_id: 'search-1',
				output: [{ type: 'output_text', text: 'results' }]
			}
		]);

		expect(items).toHaveLength(1);
		expect(items[0].type).toBe('detail_single');
	});
});
