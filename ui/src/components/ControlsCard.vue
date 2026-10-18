<!-- The controls (on the Status tab): start, standby, pause, continue, restart, and terminate -->
<script setup>
import { computed, ref } from "vue";
import { api } from "../api.js";
import { confirm, notify } from "../notify.js";
import { serverText, t } from "../i18n.js";
import { refreshStatus, status } from "../status.js";
import { mdiPause, mdiPlay, mdiPower, mdiPowerSleep, mdiRestart, mdiStop } from "../icons.js";

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
		name: "restart", label: t("controls.restart"), icon: mdiRestart, color: "warning",
		confirm: t("controls.restartConfirm"),
	},
];

const allowed = (name) => s.value?.allowed.includes(name);

async function run(command) {
	if (command.confirm && !await confirm(command.confirm, { title: command.label, color: command.color })) {
		return;
	}
	busy.value = command.name;
	try {
		await api.getText(`/command/${command.name}`);
		await refreshStatus();
	} catch (err) {
		notify(t("controls.failed", { command: command.label, error: err.message }), "error", 6000);
	} finally {
		busy.value = "";
	}
}

async function terminate(type) {
	const restart = s.value?.restart ? `\n${t("controls.restartAfter")}` : "";
	const video = s.value?.imagesAvailable ? serverText(s.value.videoMessage, s.value.videoMessageCode) : t("controls.noImages");
	const text = type === "graceful" ? t("controls.gracefulText", { video }) + restart : t("controls.forcedText");
	const ok = await confirm(text, { title: type === "graceful" ? t("controls.graceful") : t("controls.forced"), color: "error" });
	if (!ok) {
		return;
	}
	try {
		await api.getText(type === "graceful" ? "/terminate/terminateg" : "/terminate/terminatef");
	} catch {
		// A forced terminate may end duetLapse3 before it answers
	}
	if (type === "forced" || !s.value?.restart) {
		stopped.value = true;
	}
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
					<v-btn :prepend-icon="mdiStop" color="success" variant="tonal" :disabled="stopped" @click="terminate('graceful')">
						{{ t("controls.graceful") }}
					</v-btn>
					<v-btn :prepend-icon="mdiPower" color="error" variant="tonal" :disabled="stopped" @click="terminate('forced')">
						{{ t("controls.forced") }}
					</v-btn>
				</div>
			</template>
		</v-card-text>
	</v-card>
</template>
