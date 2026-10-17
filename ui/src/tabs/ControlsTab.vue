<!-- Controls tab: start, standby, pause, continue, restart, and terminate -->
<script setup>
import { computed, ref } from "vue";
import { api } from "../api.js";
import { confirm, notify } from "../notify.js";
import { refreshStatus, status } from "../status.js";
import { mdiPause, mdiPlay, mdiPower, mdiPowerSleep, mdiRestart, mdiStop } from "../icons.js";

const s = computed(() => status.data);
const busy = ref("");
const stopped = ref(false);

const commands = [
	{ name: "start", label: "Start", icon: mdiPlay, color: "success" },
	{
		name: "standby", label: "Standby", icon: mdiPowerSleep, color: "warning",
		confirm: "Standby does NOT create a video.\nAll captured images will be deleted.",
	},
	{ name: "pause", label: "Pause", icon: mdiPause, color: "info" },
	{ name: "continue", label: "Continue", icon: mdiPlay, color: "info" },
	{
		name: "restart", label: "Restart", icon: mdiRestart, color: "warning",
		confirm: "Restart will try to create a video, then get ready for the next print.\n\nAll captured images will be deleted, unless keepfiles is set.",
	},
];

const allowed = (name) => s.value?.allowed.includes(name);
const shown = computed(() => commands.filter((c) => !s.value?.hideButtons || allowed(c.name)));

async function run(command) {
	if (command.confirm && !await confirm(command.confirm, { title: command.label, color: command.color })) {
		return;
	}
	busy.value = command.name;
	try {
		await api.getText(`/command/${command.name}`);
		await refreshStatus();
	} catch (err) {
		notify(`${command.label} failed: ${err.message}`, "error", 6000);
	} finally {
		busy.value = "";
	}
}

async function terminate(type) {
	const restart = s.value?.restart ? "\nA restart will occur after the terminate." : "";
	const text = type === "graceful"
		? `Make the video and terminate.\n${s.value?.imagesAvailable ? s.value.videoMessage : "There are no images available."}${restart}`
		: "Terminate straight away.\nA video will NOT be created.";
	const ok = await confirm(text, { title: type === "graceful" ? "Graceful terminate" : "Forced terminate", color: "error" });
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
	<v-row v-if="s">
		<v-col cols="12" md="7">
			<v-card>
				<v-card-title>Controls</v-card-title>
				<v-card-subtitle>
					duetLapse3 is in the <strong>{{ s.action }}</strong> state - capture status {{ s.printState }}
				</v-card-subtitle>
				<v-card-text class="d-flex flex-wrap ga-2">
					<v-btn v-for="c in shown" :key="c.name" :prepend-icon="c.icon" :color="c.color" variant="tonal"
						   :disabled="!allowed(c.name) || stopped" :loading="busy === c.name" @click="run(c)">
						{{ c.label }}
					</v-btn>
				</v-card-text>
			</v-card>
		</v-col>
		<v-col v-if="s.canTerminate" cols="12" md="5">
			<v-card>
				<v-card-title>Terminate</v-card-title>
				<v-card-text>
					<v-alert v-if="stopped" type="info" variant="tonal" class="mb-3">duetLapse3 is stopping.</v-alert>
					<div class="d-flex flex-wrap ga-2">
						<v-btn :prepend-icon="mdiStop" color="success" variant="tonal" :disabled="stopped" @click="terminate('graceful')">
							Graceful terminate
						</v-btn>
						<v-btn :prepend-icon="mdiPower" color="error" variant="tonal" :disabled="stopped" @click="terminate('forced')">
							Forced terminate
						</v-btn>
					</div>
				</v-card-text>
			</v-card>
		</v-col>
	</v-row>
	<v-progress-linear v-else indeterminate color="primary"></v-progress-linear>
</template>
