<!-- The duetLapse3 page: the tabs, the shown tab, then the message bar and confirm dialog -->
<script setup>
import { computed, ref, watch } from "vue";
import { query } from "./env.js";
import { api } from "./api.js";
import { serverText, t } from "./i18n.js";
import { closeConfirm, confirmState, snackbar } from "./notify.js";
import { startStatus, status } from "./status.js";
import { startVideoAlerts } from "./videos.js";
import VideoAlert from "./components/VideoAlert.vue";
import PrinterConnect from "./components/PrinterConnect.vue";
import {
	mdiCctv, mdiClose, mdiCog, mdiFolder, mdiVideo, mdiViewDashboard,
} from "./icons.js";
import StatusTab from "./tabs/StatusTab.vue";
import VideoTab from "./tabs/VideoTab.vue";
import CamerasTab from "./tabs/CamerasTab.vue";
import ConfigTab, { configTabs } from "./tabs/ConfigTab.vue";
import FilesTab, { fileTabs } from "./tabs/FilesTab.vue";

const tabs = [
	{ value: "status", title: t("tabs.status"), icon: mdiViewDashboard, component: StatusTab },
	{ value: "video", title: t("tabs.video"), icon: mdiVideo, component: VideoTab },
	{ value: "cameras", title: t("tabs.cameras"), icon: mdiCctv, component: CamerasTab },
	{ value: "config", title: t("tabs.config"), icon: mdiCog, component: ConfigTab },
	{ value: "files", title: t("tabs.filesTop"), icon: mdiFolder, component: FilesTab },
];

// ?tab=<name> opens that tab.  Otherwise the tab is remembered when the page is reloaded (e.g. when DWC shows it again)
function savedTab() {
	try {
		if (configTabs.includes(query.get("tab"))) {
			return "config";
		}
		if (fileTabs.includes(query.get("tab"))) {
			return "files";
		}
		const tab = query.get("tab") || sessionStorage.getItem("duetLapse3.tab");
		return tabs.some((t) => t.value === tab) ? tab : "status";
	} catch {
		return "status";
	}
}
const tab = ref(savedTab());
const current = computed(() => tabs.find((t) => t.value === tab.value));
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
				<v-alert v-if="status.data?.settingsAlert" type="error" variant="tonal" closable class="mb-4" @click:close="api.postJson('/settings/alert/clear', {})">
					<div><strong>{{ t("settingsAlert.notApplied") }}</strong></div>
					{{ serverText(status.data.settingsAlert, status.data.settingsAlertCode) }}
				</v-alert>
				<PrinterConnect></PrinterConnect>
				<component :is="current.component" v-bind="current.props" :key="current.value"></component>
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
					<v-btn @click="closeConfirm(false)">{{ t("common.cancel") }}</v-btn>
					<v-btn :color="confirmState.color" variant="flat" @click="closeConfirm(true)">{{ t("common.ok") }}</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>
	</v-app>
</template>
