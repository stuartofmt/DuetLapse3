// Builds the duetLapse3 web interface into the plugin's static folder.
//
//   npm install      once, to install Vue / Vuetify / Vite
//   npm run build    writes the page and assets/ to Code/dsf/static/app
//   npm run dev      live-reload server at http://localhost:5173/static/app/index.html - set DUETLAPSE3_URL
//                    to a running duetLapse3 (default http://localhost:17800) for the API, images and files
//
// The built files are committed, so the plugin needs no Node.js and no internet access to run.

import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vuetify from "vite-plugin-vuetify";

const duetLapse3Url = process.env.DUETLAPSE3_URL || "http://localhost:17800";

export default defineConfig({
	// duetLapse3 serves the built page from /static/app (and index.html at /)
	base: "/static/app/",
	plugins: [
		vue(),
		// Only the Vuetify components that are used end up in the bundle.
		vuetify({ autoImport: true }),
	],
	build: {
		outDir: fileURLToPath(new URL("../Code/dsf/static/app", import.meta.url)),
		emptyOutDir: true,
	},
	server: {
		proxy: {
			// Everything outside /static/app (API, commands, images, files) goes to the running duetLapse3.
			"^/(?!static/app/).*": { target: duetLapse3Url, changeOrigin: true },
		},
	},
});
