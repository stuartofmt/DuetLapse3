<!-- The message announcing videos made (or not) - see videos.js -->
<script setup>
import { computed } from "vue";
import { fileUrl } from "../api.js";
import { videoAlert } from "../videos.js";
import { serverText, t } from "../i18n.js";
import { mdiAlertCircle, mdiCheckCircle, mdiClose, mdiOpenInNew } from "../icons.js";

const allOk = computed(() => videoAlert.events.every((e) => e.ok));
const noneOk = computed(() => videoAlert.events.every((e) => !e.ok));
const title = computed(() => {
	const made = videoAlert.events.filter((e) => e.ok).length;
	if (noneOk.value) return t("videoAlert.notCreated");
	return t("videoAlert.created", { n: made });
});
const color = computed(() => (allOk.value ? "success" : noneOk.value ? "error" : "warning"));
</script>

<template>
	<v-snackbar v-model="videoAlert.show" :color="color" location="top end" :timeout="15000" multi-line max-width="520">
		<div class="text-subtitle-1 font-weight-bold mb-1">{{ title }}</div>
		<div v-for="e in videoAlert.events" :key="e.seq" class="d-flex align-center ga-2 py-1">
			<v-icon :icon="e.ok ? mdiCheckCircle : mdiAlertCircle" size="small"></v-icon>
			<span class="flex-grow-1 dl3-break">{{ e.ok ? e.name : serverText(e.message, e.messageCode) }}</span>
			<v-btn v-if="e.ok" :href="fileUrl(e.file)" target="_blank" :prepend-icon="mdiOpenInNew" variant="text" size="small">{{ t("videoAlert.open") }}</v-btn>
		</div>
		<template #actions>
			<v-btn variant="text" :icon="mdiClose" @click="videoAlert.show = false"></v-btn>
		</template>
	</v-snackbar>
</template>
