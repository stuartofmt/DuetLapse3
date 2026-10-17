<!-- Video tab: make a video now (one button per camera when there are two), and the Video settings -->
<script setup>
import { computed, ref } from "vue";
import { notify } from "../notify.js";
import { requestVideo } from "../videos.js";
import { refreshStatus, status } from "../status.js";
import SettingsForm from "../components/SettingsForm.vue";
import { mdiMovieOpen } from "../icons.js";

const s = computed(() => status.data);
const making = ref(""); // The snapshot being made: "all", "1" or "2"

// Images captured by each camera in use (or that has images), against the number needed for a video
const counts = computed(() => {
	if (!s.value) return [];
	const list = [{ number: 1, name: "Camera1", images: s.value.frames, active: s.value.camera1 }];
	if (s.value.camera2 || s.value.frames2 > 0) {
		list.push({ number: 2, name: "Camera2", images: s.value.frames2, active: s.value.camera2 });
	}
	return list.map((c) => ({ ...c, enough: c.images >= s.value.imagesNeeded, percent: Math.min(100, (100 * c.images) / s.value.imagesNeeded) }));
});
const twoCameras = computed(() => counts.value.length > 1);

// Snapshot needs a camera with enough images for a video
const enough = computed(() => counts.value.some((c) => c.enough));

// minvideo can't be more than maxvideo - unless maxvideo is 0 (off)
function videoCheck(v) {
	const min = Number(v.minvideo), max = Number(v.maxvideo);
	if (max > 0 && min > max) {
		return { minvideo: `minvideo can not be more than maxvideo (${max})`, maxvideo: `maxvideo must be 0 (off) or at least minvideo (${min})` };
	}
	return {};
}
// The minvideo arrows stop at maxvideo
const videoLimits = (v, key) => (key === "minvideo" && Number(v.maxvideo) > 0 ? { max: Number(v.maxvideo) } : {});

// camera 1 or 2 makes that camera's video only - otherwise every camera's
async function snapshot(camera) {
	making.value = camera ? String(camera) : "all";
	try {
		await requestVideo(camera ? `/snapshot?camera=${camera}` : "/snapshot");  // The result is announced
	} catch (err) {
		notify(`Snapshot failed: ${err.message}`, "error", 6000);
	} finally {
		making.value = "";
	}
}
</script>

<template>
	<v-row justify="center">
		<v-col cols="12" md="10" lg="8">
			<v-card class="mb-4">
				<v-card-title>Make a video now</v-card-title>
				<v-card-text>
					<div v-for="c in counts" :key="c.name" class="mb-4">
						<div class="d-flex justify-space-between align-center flex-wrap ga-2 text-body-2 mb-1">
							<span><strong>{{ c.name }}</strong>{{ c.active ? "" : " (not in use)" }}: {{ c.images }} images captured</span>
							<span class="d-flex align-center ga-3">
								<span :class="c.enough ? 'text-success' : 'text-medium-emphasis'">{{ s.imagesNeeded }} needed for a video</span>
								<v-btn v-if="twoCameras" :prepend-icon="mdiMovieOpen" color="primary" variant="tonal" size="small"
									   :loading="making === String(c.number)" :disabled="!c.enough || making !== ''"
									   @click="snapshot(c.number)">Snapshot</v-btn>
							</span>
						</div>
						<v-progress-linear :model-value="c.percent" :color="c.enough ? 'success' : 'primary'" height="8" rounded></v-progress-linear>
					</div>
					<p class="mb-3">{{ s?.videoMessage }}</p>
					<template v-if="!twoCameras">
						<v-btn :prepend-icon="mdiMovieOpen" color="primary" variant="tonal" :loading="making === 'all'"
							   :disabled="!s?.imagesAvailable || !enough" @click="snapshot()">Snapshot</v-btn>
						<span v-if="s && !s.imagesAvailable" class="text-medium-emphasis ms-3">No images have been captured yet</span>
						<span v-else-if="s && !enough" class="text-medium-emphasis ms-3">Not enough images yet - {{ s.imagesNeeded }} are needed</span>
					</template>
					<p v-else-if="s && !enough" class="text-medium-emphasis">Not enough images yet - {{ s.imagesNeeded }} are needed for each camera's video</p>
				</v-card-text>
			</v-card>
			<SettingsForm tab="video" save-url="/video/save" :check="videoCheck" :limits="videoLimits" @saved="refreshStatus"></SettingsForm>
		</v-col>
	</v-row>
</template>
