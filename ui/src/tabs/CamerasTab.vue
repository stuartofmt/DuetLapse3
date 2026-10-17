<!-- Cameras tab: each camera's url with a preview. Save puts the urls in duetLapse3.json and uses them straight away -->
<script setup>
import { onMounted, reactive, ref } from "vue";
import { api } from "../api.js";
import { notify } from "../notify.js";
import { refreshStatus } from "../status.js";
import { mdiCameraOff, mdiContentSave, mdiImageRefresh } from "../icons.js";

const cameras = ref([]);
const urls = reactive({});
const previews = reactive({});   // key: preview image url ('' = no camera)
const failed = reactive({});     // key: true if the preview did not load
const errors = reactive({});
const configFile = ref("");
const alert = reactive({ text: "", type: "success" });
const saving = ref(false);

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
		configFile.value = data.configFile;
		for (const c of data.cameras) {
			urls[c.key] = c.url;
			preview(c.key);
		}
		if (data.error) {
			Object.assign(alert, { text: data.error, type: "error" });
		}
	} catch (err) {
		Object.assign(alert, { text: `Could not read the cameras: ${err.message}`, type: "error" });
	}
}

async function save() {
	Object.keys(errors).forEach((key) => delete errors[key]);
	saving.value = true;
	try {
		const result = await api.postJson("/cameras/save", { ...urls });
		Object.assign(alert, { text: result.message, type: "success" });
		notify(result.message);
		cameras.value.forEach((c) => preview(c.key));
		refreshStatus();
	} catch (err) {
		if (err.status === 400 && err.data?.errors) {
			Object.assign(errors, err.data.errors);
			Object.assign(alert, { text: err.data.errors[""] || "Not saved - check the urls marked in red.", type: "error" });
		} else {
			Object.assign(alert, { text: `Could not save: ${err.message}`, type: "error" });
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
					<v-card-title>Camera{{ c.number }}</v-card-title>
					<v-card-text>
						<v-text-field v-model="urls[c.key]" :label="`${c.key} - camera url`" :hint="c.help" persistent-hint
									  :error-messages="errors[c.key]" placeholder="http://..." persistent-placeholder
									  variant="outlined" density="comfortable" class="mb-4" @keydown.enter="preview(c.key)"></v-text-field>
						<div class="dl3-media">
							<a v-if="previews[c.key] && !failed[c.key]" :href="previews[c.key]" target="_blank">
								<img :src="previews[c.key]" alt="Camera preview" @error="failed[c.key] = true">
							</a>
							<div v-else class="dl3-media-overlay">
								<v-icon :icon="mdiCameraOff" size="40"></v-icon>
								<span>{{ previews[c.key] ? "No image from this url" : "No camera" }}</span>
							</div>
						</div>
					</v-card-text>
					<v-card-actions>
						<v-btn :prepend-icon="mdiImageRefresh" @click="preview(c.key)">Preview</v-btn>
						<v-spacer></v-spacer>
						<v-btn :prepend-icon="mdiContentSave" :loading="saving" @click="save">Save</v-btn>
					</v-card-actions>
				</v-card>
			</v-col>
		</v-row>
		<p class="text-caption text-medium-emphasis">
			Use a snapshot url (preferred) or an MJPEG stream url. Save saves both cameras.
			Settings file: {{ configFile }}
		</p>
	</div>
</template>
