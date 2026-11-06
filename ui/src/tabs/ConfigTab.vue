<!-- Config tab: its own tabs (General, Image Capture, Execution, Files), each with the settings in the sections it picks (see /api/settings) -->
<script>
export const configTabs = ["capture", "execution", "filesettings"];  // Besides General (config).  ?tab=<name> opens these too - ?tab=files is the main Files tab
let opened = false;  // ?tab= only picks the tab the first time - this stays when the tab is left and come back to
</script>

<script setup>
import { ref, watch } from "vue";
import SettingsForm from "../components/SettingsForm.vue";
import { query } from "../env.js";
import { t } from "../i18n.js";
import { mdiCameraTimer, mdiCog, mdiFileCog, mdiTune } from "../icons.js";

const tabs = [
	{ value: "config", title: t("tabs.general"), icon: mdiCog },
	{ value: "capture", title: t("tabs.capture"), icon: mdiCameraTimer },
	{ value: "execution", title: t("tabs.execution"), icon: mdiTune },
	{ value: "files", title: t("tabs.files"), icon: mdiFileCog },
];

// Remembered as for the main tabs
function savedTab() {
	const asked = opened ? null : query.get("tab");
	opened = true;
	if (asked === "config" || configTabs.includes(asked)) {
		return asked === "filesettings" ? "files" : asked;
	}
	try {
		const saved = sessionStorage.getItem("duetLapse3.configTab");
		return tabs.some((t) => t.value === saved) ? saved : "config";
	} catch {
		return "config";
	}
}
const tab = ref(savedTab());
watch(tab, (value) => {
	try {
		sessionStorage.setItem("duetLapse3.configTab", value);
	} catch {
		// Not available - the tab is just not remembered
	}
});
</script>

<template>
	<v-row justify="center">
		<v-col cols="12" md="10" lg="8">
			<v-tabs v-model="tab" color="primary" density="compact" show-arrows class="mb-4">
				<v-tab v-for="t in tabs" :key="t.value" :value="t.value" :prepend-icon="t.icon">{{ t.title }}</v-tab>
			</v-tabs>
			<v-alert type="info" variant="tonal" density="compact" class="mb-4">
				{{ t("config.restartNeeded") }}
			</v-alert>
			<SettingsForm :tab="tab" :key="tab" save-url="/config/save"></SettingsForm>
		</v-col>
	</v-row>
</template>
