<script lang="ts">
	export let value: Record<string, unknown> = {};
</script>

<div id="model-subscription-policy" class="flex flex-col gap-2 text-sm">
	<div class="font-medium">Subscription Policy</div>
	<pre class="overflow-auto rounded border p-2 text-xs">{JSON.stringify(value ?? {}, null, 2)}</pre>
</div>
