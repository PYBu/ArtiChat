<script lang="ts">
	export let subscription: any = null;

	$: total =
		(subscription?.plan_balance_micros ?? 0) + (subscription?.check_balance_micros ?? 0);
	$: exhausted = total <= 0;
</script>

<button
	id="subscription-quota-ring"
	class="flex h-8 w-8 items-center justify-center rounded-full border text-xs"
	class:border-red-500={exhausted}
	type="button"
>
	<span>{subscription?.tier?.[0]?.toUpperCase() ?? '-'}</span>
</button>
