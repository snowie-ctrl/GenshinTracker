<script lang="ts">
	import { imgSrc } from './img';

	let { icon, label, base, bonus = 0, testid }: {
		icon: string | null; label: string; base: number; bonus?: number; testid?: string;
	} = $props();
</script>

<div class="badge" data-testid={testid}>
	<div class="ic">{#if imgSrc(icon)}<img src={imgSrc(icon)} alt="" />{/if}</div>
	<span class="lv" class:crown={base >= 10}>{base}{#if bonus}<small> +{bonus}</small>{/if}</span>
	<span class="label">{label}</span>
</div>

<style>
	.badge { display: flex; flex-direction: column; align-items: center; gap: 4px; width: 76px; text-align: center; }
	.ic { width: 52px; height: 52px; border-radius: 50%; background: rgba(255, 255, 255, 0.07);
		border: 1px solid var(--glass-border); display: flex; align-items: center; justify-content: center; }
	.ic img { width: 42px; height: 42px; }
	.lv { font-size: 16px; font-weight: 700; }
	.lv.crown { color: var(--gold); }
	.lv small { color: var(--el, var(--gold)); font-size: 12px; }
	.label { font-size: 11px; color: var(--muted); }
</style>
