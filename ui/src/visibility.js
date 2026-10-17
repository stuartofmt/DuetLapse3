// visibility.visible is false while the browser tab is hidden or, inside DWC, while DWC shows a different
// page (DWC posts { source: 'duetLapse3', type: 'visibility', visible }). The page stops polling while hidden.
import { reactive } from "vue";
import { embedded, PLUGIN } from "./env.js";

export const visibility = reactive({ visible: !document.hidden });
let parentVisible = true;

function updateVisibility() {
	visibility.visible = !document.hidden && parentVisible;
}

document.addEventListener("visibilitychange", updateVisibility);
if (embedded) {
	window.addEventListener("message", (event) => {
		const msg = event.data;
		if (event.source === window.parent && msg?.source === PLUGIN && msg.type === "visibility") {
			parentVisible = Boolean(msg.visible);
			updateVisibility();
		}
	});
}
