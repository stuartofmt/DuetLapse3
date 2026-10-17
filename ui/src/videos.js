// Announces each video duetLapse3 makes (or fails to make), wherever it was started: the end of a print, a restart,
// a gcode command, or this page. The results come with the status (/api/status videoEvents). What has been shown
// is remembered in the browser, so videos made while the page was closed are announced when it is next opened.
import { reactive, watch } from "vue";
import { api } from "./api.js";
import { notify } from "./notify.js";
import { refreshStatus, status } from "./status.js";

const KEY = "duetLapse3.videosSeen"; // { run, seq } - the last result shown.  run changes when duetLapse3 restarts

export const videoAlert = reactive({ show: false, events: [] });

function loadSeen() {
	try {
		return JSON.parse(localStorage.getItem(KEY)) || {};
	} catch {
		return {};
	}
}
let seen = loadSeen();

function latest(data) {
	const events = data?.videoEvents ?? [];
	return { run: data?.run, seq: events.length ? events[events.length - 1].seq : 0 };
}

function announce(data) {
	if (!data?.videoEvents) return;
	const lastSeq = seen.run === data.run ? seen.seq : 0;
	const fresh = data.videoEvents.filter((e) => e.seq > lastSeq);
	if (fresh.length) {
		const shown = videoAlert.show ? videoAlert.events : [];
		videoAlert.events = [...shown, ...fresh.filter((e) => !shown.some((s) => s.seq === e.seq))];
		videoAlert.show = true;
	}
	seen = { run: data.run, seq: Math.max(lastSeq, latest(data).seq) };
	try {
		localStorage.setItem(KEY, JSON.stringify(seen));
	} catch {
		// Not remembered - videos may be announced again after a reload
	}
}

export function startVideoAlerts() {
	watch(() => status.data, announce);
}

// Ask for a video (Snapshot, Make a video). Its result is announced like any other video's - the reply text is
// only shown if no video was attempted (e.g. "There are no images captured yet")
export async function requestVideo(url) {
	const before = latest(status.data);
	const text = await api.getText(url);
	await refreshStatus();
	const after = latest(status.data);
	if (after.run === before.run && after.seq === before.seq && text.trim()) {
		notify(text.trim(), "info", 8000);
	}
}
