// The duetLapse3 status (as /api/status) for every tab, and the changes the tabs refresh on.
// duetLapse3 sends each change as it happens over /api/events (Server-Sent Events), while the page is visible.
// If that doesn't work (no EventSource, or it fails repeatedly without sending anything), the status is read every few seconds instead.
import { reactive, watch } from "vue";
import { api } from "./api.js";
import { t } from "./i18n.js";
import { visibility } from "./visibility.js";

const INTERVAL = 3000; // ms - only when falling back to reading the status
const FAILURES = 3;    // Errors in a row, without ever receiving anything, before falling back

export const status = reactive({ data: null, error: "" });
// Counters that change when files are deleted or zipped, and when the settings are saved
export const changes = reactive({ files: 0, settings: 0 });

let source = null;
let timer = null;
let failures = 0;
let received = false;
let polling = typeof EventSource === "undefined";

export async function refreshStatus() {
	try {
		status.data = await api.get("/api/status");
		status.error = "";
	} catch (err) {
		status.error = err.status ? err.message : t("common.notAnswering");
	}
}

function listen() {
	source = new EventSource("/api/events");
	const on = (name, handler) => source.addEventListener(name, (event) => {
		received = true;
		failures = 0;
		status.error = "";
		handler(JSON.parse(event.data));
	});
	on("status", (data) => (status.data = data));
	on("files", (data) => (changes.files = data.version));
	on("settings", (data) => (changes.settings = data.version));
	source.onerror = () => {
		// EventSource reconnects by itself (e.g. after duetLapse3 restarts)
		status.error = t("common.notAnswering");
		if (!received && ++failures >= FAILURES) {
			polling = true;
			stop();
			start();
		}
	};
}

function start() {
	if (polling) {
		if (timer === null) {
			refreshStatus();
			timer = setInterval(refreshStatus, INTERVAL);
		}
	} else if (source === null) {
		listen();
	}
}

function stop() {
	clearInterval(timer);
	timer = null;
	source?.close();
	source = null;
}

export function startStatus() {
	watch(() => visibility.visible, (visible) => (visible ? start() : stop()), { immediate: true });
}
