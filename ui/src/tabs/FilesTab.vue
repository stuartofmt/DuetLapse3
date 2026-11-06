<!-- Files tab: its own tabs, Images and Log -->
<script>
export const fileTabs = ["images", "log"];  // ?tab=<name> opens these too
let opened = false;  // ?tab= only picks the tab the first time - this stays when the tab is left and come back to
</script>

<script setup>
import { computed, ref, watch } from "vue";
import { query } from "../env.js";
import { t } from "../i18n.js";
import { mdiImageMultiple, mdiTextBoxOutline } from "../icons.js";
import ImagesTab from "./ImagesTab.vue";
import LogTab from "./LogTab.vue";

const tabs = [
	{ value: "images", title: t("tabs.images"), icon: mdiImageMultiple, component: ImagesTab },
	{ value: "log", title: t("tabs.log"), icon: mdiTextBoxOutline, component: LogTab },
];

// Remembered as for the main tabs
function savedTab() {
	const asked = opened ? null : query.get("tab");
	opened = true;
	if (fileTabs.includes(asked)) {
		return asked;
	}
	try {
		const saved = sessionStorage.getItem("duetLapse3.filesTab");
		return fileTabs.includes(saved) ? saved : "images";
	} catch {
		return "images";
	}
}
const tab = ref(savedTab());
const current = computed(() => tabs.find((t) => t.value === tab.value));
watch(tab, (value) => {
	try {
		sessionStorage.setItem("duetLapse3.filesTab", value);
	} catch {
		// Not available - the tab is just not remembered
	}
});
</script>

<template>
	<v-tabs v-model="tab" color="primary" density="compact" show-arrows class="mb-4">
		<v-tab v-for="t in tabs" :key="t.value" :value="t.value" :prepend-icon="t.icon">{{ t.title }}</v-tab>
	</v-tabs>
	<component :is="current.component" :key="current.value"></component>
</template>
