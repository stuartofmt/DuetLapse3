<!-- The controls (on the Status tab): start, standby, pause, continue, print complete, and terminate -->
<script setup>
import { computed, ref } from "vue";
import { api } from "../api.js";
import { confirm, notify } from "../notify.js";
import { t } from "../i18n.js";
import { refreshStatus, status } from "../status.js";
import { mdiFlagCheckered, mdiPause, mdiPlay, mdiPower, mdiPowerSleep } from "../icons.js";

const s = computed(() => status.data);
const busy = ref("");
const stopped = ref(false);

const commands = [
	{ name: "start", label: t("controls.start"), icon: mdiPlay, color: "success" },
	{
		name: "standby", label: t("controls.standby"), icon: mdiPowerSleep, color: "warning",
		confirm: t("controls.standbyConfirm"),
	},
	{ name: "pause", label: t("controls.pause"), icon: mdiPause, color: "info" },
	{ name: "continue", label: t("controls.continue"), icon: mdiPlay, color: "info" },
	{
		name: "printcomplete", label: t("controls.printcomplete"), icon: mdiFlagCheckered, color: "warning",
		// What happens depends on On Print Complete
		confirm: () => s.value?.onPrintComplete === "terminate" ? t("controls.printcompleteTerminate")
			: t("controls.printcompleteConfirm", { next: t(s.value?.onPrintComplete === "standby" ? "controls.thenStandby" : "controls.thenReady") }),
	},
];

const allowed = (name) => s.value?.allowed.includes(name);

async function run(command) {
	const text = typeof command.confirm === "function" ? command.confirm() : command.confirm;
	if (text && !await confirm(text, { title: command.label, color: command.color })) {
		return;
	}
	const ending = command.name === "printcomplete" && s.value?.onPrintComplete === "terminate";  // duetLapse3 will stop
	busy.value = command.name;
	try {
		await api.getText(`/command/${command.name}`);
		if (ending) {
			stopped.value = true;
			return;
		}
		await refreshStatus();
	} catch (err) {
		if (ending) {  // It may end before it answers
			stopped.value = true;
			return;
		}
		notify(t("controls.failed", { command: command.label, error: err.message }), "error", 6000);
	} finally {
		busy.value = "";
	}
}

async function terminate() {
	if (!await confirm(t("controls.forcedText"), { title: t("controls.forced"), color: "error" })) {
		return;
	}
	try {
		await api.getText("/terminate/terminatef");
	} catch {
		// duetLapse3 may end before it answers
	}
	stopped.value = true;
}
</script>

<template>
	<v-card v-if="s">
		<v-card-title>{{ t("controls.title") }}</v-card-title>
		<v-card-text>
			<v-alert v-if="stopped" type="info" variant="tonal" density="compact" class="mb-3">{{ t("controls.stopping") }}</v-alert>
			<div class="d-flex flex-wrap ga-2">
				<v-btn v-for="c in commands" :key="c.name" :prepend-icon="c.icon" :color="c.color" variant="tonal"
					   :disabled="!allowed(c.name) || stopped" :loading="busy === c.name" @click="run(c)">
					{{ c.label }}
				</v-btn>
			</div>
			<template v-if="s.canTerminate">
				<v-divider class="my-3"></v-divider>
				<div class="d-flex flex-wrap ga-2">
					<v-btn :prepend-icon="mdiPower" color="error" variant="tonal" :disabled="stopped" @click="terminate">
						{{ t("controls.forced") }}
					</v-btn>
				</div>
			</template>
		</v-card-text>
	</v-card>
</template>
