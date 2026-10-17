<!-- The duetLapse3 page: the tabs, the shown tab, then the message bar and confirm dialog -->
<script setup>
import { ref, watch } from "vue";
import { query } from "./env.js";
import { closeConfirm, confirmState, snackbar } from "./notify.js";
import { startStatus, status } from "./status.js";
import { startVideoAlerts } from "./videos.js";
import VideoAlert from "./components/VideoAlert.vue";
import {
	mdiCctv, mdiClose, mdiCog, mdiFolderMultiple, mdiInformation, mdiVideo, mdiViewDashboard,
} from "./icons.js";
import StatusTab from "./tabs/StatusTab.vue";
import VideoTab from "./tabs/VideoTab.vue";
import FilesTab from "./tabs/FilesTab.vue";
import InfoTab from "./tabs/InfoTab.vue";
import CamerasTab from "./tabs/CamerasTab.vue";
import ConfigTab from "./tabs/ConfigTab.vue";

const tabs = [
	{ value: "status", title: "Status", icon: mdiViewDashboard, component: StatusTab },
	{ value: "video", title: "Video", icon: mdiVideo, component: VideoTab },
	{ value: "files", title: "Files", icon: mdiFolderMultiple, component: FilesTab },
	{ value: "info", title: "Info", icon: mdiInformation, component: InfoTab },
	{ value: "cameras", title: "Cameras", icon: mdiCctv, component: CamerasTab },
	{ value: "config", title: "Config", icon: mdiCog, component: ConfigTab },
];

// ?tab=<name> opens that tab.  Otherwise the tab is remembered when the page is reloaded (e.g. when DWC shows it again)
function savedTab() {
	try {
		const tab = query.get("tab") || sessionStorage.getItem("duetLapse3.tab");
		return tabs.some((t) => t.value === tab) ? tab : "status";
	} catch {
		return "status";
	}
}
const tab = ref(savedTab());
watch(tab, (value) => {
	try {
		sessionStorage.setItem("duetLapse3.tab", value);
	} catch {
		// Not available - the tab is just not remembered
	}
});

startStatus();
startVideoAlerts();
</script>

<template>
	<v-app>
		<v-main>
			<v-tabs v-model="tab" color="primary" density="compact" show-arrows>
				<v-tab v-for="t in tabs" :key="t.value" :value="t.value" :prepend-icon="t.icon">{{ t.title }}</v-tab>
			</v-tabs>
			<v-divider></v-divider>
			<v-container fluid class="pa-2 pa-sm-4">
				<v-alert v-if="status.error" type="error" variant="tonal" class="mb-4">{{ status.error }}</v-alert>
				<component :is="tabs.find((t) => t.value === tab).component"></component>
			</v-container>
		</v-main>

		<VideoAlert></VideoAlert>

		<v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="snackbar.timeout">
			<span style="white-space: pre-line">{{ snackbar.text }}</span>
			<template #actions>
				<v-btn variant="text" :icon="mdiClose" @click="snackbar.show = false"></v-btn>
			</template>
		</v-snackbar>

		<v-dialog :model-value="confirmState.show" max-width="460" @update:model-value="closeConfirm(false)">
			<v-card>
				<v-card-title>{{ confirmState.title }}</v-card-title>
				<v-card-text style="white-space: pre-line">{{ confirmState.text }}</v-card-text>
				<v-card-actions>
					<v-spacer></v-spacer>
					<v-btn @click="closeConfirm(false)">Cancel</v-btn>
					<v-btn :color="confirmState.color" variant="flat" @click="closeConfirm(true)">OK</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>
	</v-app>
</template>
