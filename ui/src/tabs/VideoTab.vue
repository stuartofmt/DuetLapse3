<!-- Video tab: make a video now, and the Video and Overrides settings (used straight away when saved) -->
<script setup>
import { computed, ref } from "vue";
import { api } from "../api.js";
import { notify } from "../notify.js";
import { refreshStatus, status } from "../status.js";
import SettingsForm from "../components/SettingsForm.vue";
import { mdiMovieOpen } from "../icons.js";

const s = computed(() => status.data);
const making = ref(false);

async function snapshot() {
	making.value = true;
	try {
		const result = await api.getText("/snapshot");
		notify(result.trim() || "Done", result.toLowerCase().includes("error") ? "error" : "success", 8000);
	} catch (err) {
		notify(`Snapshot failed: ${err.message}`, "error", 6000);
	} finally {
		making.value = false;
	}
}
</script>

<template>
	<v-row justify="center">
		<v-col cols="12" md="10" lg="8">
			<v-card class="mb-4">
				<v-card-title>Make a video now</v-card-title>
				<v-card-text>
					<p class="mb-3">{{ s?.videoMessage }}</p>
					<v-btn :prepend-icon="mdiMovieOpen" color="primary" variant="tonal" :loading="making"
						   :disabled="!s?.imagesAvailable" @click="snapshot">Snapshot</v-btn>
					<span v-if="s && !s.imagesAvailable" class="text-medium-emphasis ms-3">No images have been captured yet</span>
				</v-card-text>
			</v-card>
			<SettingsForm tab="video" save-url="/video/save" @saved="refreshStatus"></SettingsForm>
		</v-col>
	</v-row>
</template>
