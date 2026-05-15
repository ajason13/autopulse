// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://ajason13.github.io',
	base: '/autopulse/',
	integrations: [
		starlight({
			title: 'AutoPulse Docs',
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/ajason13/autopulse' }],
			sidebar: [
				{
					label: 'Guides',
					items: [
						// Each item here is one entry in the navigation menu.
						{ label: 'Example Guide', slug: 'guides/example' },
					],
				},
				{
					label: 'Specs',
					items: [{ autogenerate: { directory: 'specs' } }],
				},
				{
					label: 'Reference',
					items: [{ autogenerate: { directory: 'reference' } }],
				},
			],
		}),
	],
});
