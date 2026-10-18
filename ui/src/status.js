// The duetLapse3 status (/api/status), read every few seconds while the page is visible, for every tab.
import { reactive, watch } from "vue";
import { api } from "./api.js";
import { t } from "./i18n.js";
import { visibility } from "./visibility.js";

const INTERVAL = 3000; // ms

export const status = reactive({ data: null, error: "" });
let timer = null;

export async function refreshStatus() {
	try {
		status.data = await api.get("/api/status");
		status.error = "";
	} catch (err) {
		status.error = err.status ? err.message : t("common.notAnswering");
	}
}

function start() {
	if (timer === null) {
		refreshStatus();
		timer = setInterval(refreshStatus, INTERVAL);
	}
}

function stop() {
	clearInterval(timer);
	timer = null;
}

export function startStatus() {
	watch(() => visibility.visible, (visible) => (visible ? start() : stop()), { immediate: true });
}
