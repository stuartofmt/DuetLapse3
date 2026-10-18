<!-- Cameras tab: each camera's url with a preview. Save saves the urls and uses them straight away -->
<script setup>
import { onMounted, reactive, ref } from "vue";
import { api } from "../api.js";
import { notify } from "../notify.js";
import { serverText, settingDescription, settingLabel, t } from "../i18n.js";
import { refreshStatus } from "../status.js";
import { mdiCameraOff, mdiContentSave, mdiImageRefresh } from "../icons.js";

const cameras = ref([]);
const urls = reactive({});
const previews = reactive({});   // key: preview image url ('' = no camera)
const failed = reactive({});     // key: true if the preview did not load
const errors = reactive({});
const alert = reactive({ text: "", type: "success" });
const saving = ref(false);
const enabled = reactive({});    // enableKey: true / false
const switching = reactive({});

// Switch a camera on or off - saved and used straight away (the url is kept)
async function setEnabled(c, on) {
	switching[c.enableKey] = true;
	try {
		const result = await api.postJson("/cameras/enable", { key: c.enableKey, enabled: on });
		enabled[c.enableKey] = on;
		notify(serverText(result.message, result.messageCode), on ? "success" : "info");
		refreshStatus();
	} catch (err) {
		notify(t("cameras.couldNotSwitch", { camera: `Camera${c.number}`, error: err.message }), "error", 6000);
	} finally {
		switching[c.enableKey] = false;
	}
}

// duetLapse3 fetches the image, so logins in the url, and http cameras inside an https DWC page, work
function preview(key) {
	const url = (urls[key] || "").trim();
	failed[key] = false;
	previews[key] = url ? `/camera/preview?url=${encodeURIComponent(url)}&t=${Date.now()}` : "";
}

async function load() {
	try {
		const data = await api.get("/api/cameras");
		cameras.value = data.cameras;
		for (const c of data.cameras) {
			urls[c.key] = c.url;
			enabled[c.enableKey] = c.enabled;
			preview(c.key);
		}
		if (data.error) {
			Object.assign(alert, { text: serverText(data.error, data.errorCode), type: "error" });
		}
	} catch (err) {
		Object.assign(alert, { text: t("cameras.couldNotRead", { error: err.message }), type: "error" });
	}
}

async function save() {
	Object.keys(errors).forEach((key) => delete errors[key]);
	saving.value = true;
	try {
		const result = await api.postJson("/cameras/save", { ...urls });
		const message = serverText(result.message, result.messageCode);
		Object.assign(alert, { text: message, type: "success" });
		notify(message);
		cameras.value.forEach((c) => preview(c.key));
		refreshStatus();
	} catch (err) {
		if (err.status === 400 && err.data?.errors) {
			for (const [key, text] of Object.entries(err.data.errors)) {
				errors[key] = serverText(text, err.data.errorCodes?.[key]);
			}
			Object.assign(alert, { text: errors[""] || t("cameras.checkUrls"), type: "error" });
		} else {
			Object.assign(alert, { text: t("common.couldNotSave", { error: err.message }), type: "error" });
		}
	} finally {
		saving.value = false;
	}
}

onMounted(load);
</script>

<template>
	<div>
		<v-alert v-if="alert.text" :type="alert.type" variant="tonal" closable class="mb-4" @click:close="alert.text = ''">
			{{ alert.text }}
		</v-alert>
		<v-row>
			<v-col v-for="c in cameras" :key="c.key" cols="12" md="6">
				<v-card>
					<v-card-title class="d-flex align-center">
						Camera{{ c.number }}
						<v-chip v-if="!enabled[c.enableKey]" size="small" class="ms-2" variant="tonal">{{ t("common.off") }}</v-chip>
						<v-spacer></v-spacer>
						<v-switch :model-value="enabled[c.enableKey]" :loading="switching[c.enableKey]" color="success" inset hide-details
								  density="compact" :label="enabled[c.enableKey] ? t('common.on') : t('common.off')" class="flex-grow-0"
								  @update:model-value="setEnabled(c, $event)"></v-switch>
					</v-card-title>
					<v-card-text>
						<v-text-field v-model="urls[c.key]" :label="settingLabel(c.key)" :hint="settingDescription(c.key)" persistent-hint
									  :error-messages="errors[c.key]" placeholder="http://..." persistent-placeholder
									  variant="outlined" density="comfortable" class="mb-4" @keydown.enter="preview(c.key)"></v-text-field>
						<div class="dl3-media" :style="enabled[c.enableKey] ? '' : 'opacity: 0.45'">
							<a v-if="previews[c.key] && !failed[c.key]" :href="previews[c.key]" target="_blank">
								<img :src="previews[c.key]" :alt="t('cameras.previewAlt')" @error="failed[c.key] = true">
							</a>
							<div v-else class="dl3-media-overlay">
								<v-icon :icon="mdiCameraOff" size="40"></v-icon>
								<span>{{ previews[c.key] ? t("cameras.noImageFromUrl") : t("cameras.noCamera") }}</span>
							</div>
						</div>
					</v-card-text>
					<v-card-actions>
						<v-btn :prepend-icon="mdiImageRefresh" @click="preview(c.key)">{{ t("cameras.preview") }}</v-btn>
						<v-spacer></v-spacer>
						<v-btn :prepend-icon="mdiContentSave" :loading="saving" @click="save">{{ t("common.save") }}</v-btn>
					</v-card-actions>
				</v-card>
			</v-col>
		</v-row>
		<p class="text-caption text-medium-emphasis">
			{{ t("cameras.help") }}
		</p>
	</div>
</template>
