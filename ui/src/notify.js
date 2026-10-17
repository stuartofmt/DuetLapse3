// The snackbar message and the confirm dialog, shown by App.vue.
import { reactive } from "vue";

export const snackbar = reactive({ show: false, text: "", color: "success", timeout: 4000 });

export function notify(text, color = "success", timeout = 4000) {
	Object.assign(snackbar, { show: true, text, color, timeout });
}

export function clearNotify() {
	snackbar.show = false;
}

export const confirmState = reactive({ show: false, title: "", text: "", color: "primary", resolve: null });

// Resolves true when the user confirms
export function confirm(text, { title = "Please confirm", color = "primary" } = {}) {
	confirmState.resolve?.(false);
	return new Promise((resolve) => {
		Object.assign(confirmState, { show: true, title, text, color, resolve });
	});
}

export function closeConfirm(result) {
	confirmState.show = false;
	confirmState.resolve?.(result);
	confirmState.resolve = null;
}
