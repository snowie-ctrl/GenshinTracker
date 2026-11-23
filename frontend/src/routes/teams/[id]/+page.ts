import { redirect } from '@sveltejs/kit';

export function load({ params }) {
	redirect(307, `/teams?edit=${encodeURIComponent(params.id)}`);
}
