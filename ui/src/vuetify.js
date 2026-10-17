// Vuetify set up with the same theme tokens and defaults as DWC 3.7 (as duetPrintGuard does), and mountPage() to start the page.
//
// Theme: ?theme=dark|light (added by the DWC plugin) picks the starting theme, otherwise the browser's light /
// dark preference is used. Inside DWC, DWC also posts its current theme colours to the page, so it follows
// DWC's theme, including later changes.
import "vuetify/styles";
import "./app.css";
import { createApp } from "vue";
import { createVuetify } from "vuetify";
import { aliases, mdi } from "vuetify/iconsets/mdi-svg";
import { embedded, query, PLUGIN } from "./env.js";

function prefersDark() {
	return window.matchMedia?.("(prefers-color-scheme: dark)").matches === true;
}

function createDl3Vuetify() {
	const requested = query.get("theme");
	return createVuetify({
		icons: { defaultSet: "mdi", aliases, sets: { mdi } },
		theme: {
			defaultTheme: requested === "dark" || requested === "light" ? requested : (prefersDark() ? "dark" : "light"),
			themes: {
				light: { colors: { "card-actions": "#1E88E5", "card-title": "#383838" } },
				dark: { colors: { "card-actions": "#1E88E5", "card-title": "#EEEEEE" } },
			},
		},
		defaults: {
			VCardTitle: { class: "font-weight-bold text-card-title" },
			VCardActions: { VBtn: { color: "card-actions" } },
		},
	});
}

// Follow DWC's theme: { source: 'duetLapse3', type: 'theme', dark: bool, colors: {...} }
function followParentTheme(vuetify) {
	if (embedded) {
		window.addEventListener("message", (event) => {
			const msg = event.data;
			if (event.source !== window.parent || msg?.source !== PLUGIN || msg.type !== "theme") {
				return;
			}
			const name = msg.dark ? "dark" : "light";
			const theme = vuetify.theme.themes.value[name];
			if (theme && msg.colors && typeof msg.colors === "object") {
				theme.colors = { ...theme.colors, ...msg.colors };
			}
			vuetify.theme.change(name);
		});
		// Ask DWC for its theme in case the page loaded after DWC sent it
		window.parent.postMessage({ source: PLUGIN, type: "theme-request" }, "*");
	} else if (!query.get("theme")) {
		window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
			vuetify.theme.change(e.matches ? "dark" : "light");
		});
	}
}

export function mountPage(component) {
	const vuetify = createDl3Vuetify();
	createApp(component).use(vuetify).mount("#app");
	followParentTheme(vuetify);
}
