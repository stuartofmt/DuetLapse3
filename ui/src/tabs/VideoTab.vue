<!-- Video tab: make a video now (one button per camera when there are two), and the Video settings -->
<script setup>
import { computed, ref } from "vue";
import { notify } from "../notify.js";
import { serverText, t } from "../i18n.js";
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

// min_video_seconds can't be more than video_length - unless video_length is 0 (off)
function videoCheck(v) {
	const min = Number(v.min_video_seconds), max = Number(v.video_length);
	if (max > 0 && min > max) {
		return { min_video_seconds: t("video.minTooBig", { max }), video_length: t("video.maxTooSmall", { min }) };
	}
	return {};
}
// The min_video_seconds arrows stop at video_length
const videoLimits = (v, key) => (key === "min_video_seconds" && Number(v.video_length) > 0 ? { max: Number(v.video_length) } : {});

// camera 1 or 2 makes that camera's video only - otherwise every camera's
async function snapshot(camera) {
	making.value = camera ? String(camera) : "all";
	try {
		await requestVideo(camera ? `/snapshot?camera=${camera}` : "/snapshot");  // The result is announced
	} catch (err) {
		notify(t("video.failed", { error: err.message }), "error", 6000);
	} finally {
		making.value = "";
	}
}
</script>

<template>
	<v-row justify="center">
		<v-col cols="12" md="10" lg="8">
			<v-card class="mb-4">
				<v-card-title>{{ t("video.title") }}</v-card-title>
				<v-card-text>
					<div v-for="c in counts" :key="c.name" class="mb-4">
						<div class="d-flex justify-space-between align-center flex-wrap ga-2 text-body-2 mb-1">
							<span><strong>{{ c.active ? c.name : t("video.notInUse", { camera: c.name }) }}</strong>: {{ t("video.captured", { n: c.images }) }}</span>
							<span class="d-flex align-center ga-3">
								<span :class="c.enough ? 'text-success' : 'text-medium-emphasis'">{{ t("video.needed", { n: s.imagesNeeded }) }}</span>
								<v-btn v-if="twoCameras" :prepend-icon="mdiMovieOpen" color="primary" variant="tonal" size="small"
									   :loading="making === String(c.number)" :disabled="!c.enough || making !== ''"
									   @click="snapshot(c.number)">{{ t("video.snapshot") }}</v-btn>
							</span>
						</div>
						<v-progress-linear :model-value="c.percent" :color="c.enough ? 'success' : 'primary'" height="8" rounded></v-progress-linear>
					</div>
					<p class="mb-3">{{ serverText(s?.videoMessage, s?.videoMessageCode) }}</p>
					<template v-if="!twoCameras">
						<v-btn :prepend-icon="mdiMovieOpen" color="primary" variant="tonal" :loading="making === 'all'"
							   :disabled="!s?.imagesAvailable || !enough" @click="snapshot()">{{ t("video.snapshot") }}</v-btn>
						<span v-if="s && !s.imagesAvailable" class="text-medium-emphasis ms-3">{{ t("video.noneYet") }}</span>
						<span v-else-if="s && !enough" class="text-medium-emphasis ms-3">{{ t("video.notEnough", { n: s.imagesNeeded }) }}</span>
					</template>
					<p v-else-if="s && !enough" class="text-medium-emphasis">{{ t("video.notEnoughEach", { n: s.imagesNeeded }) }}</p>
				</v-card-text>
			</v-card>
			<SettingsForm tab="video" save-url="/video/save" :check="videoCheck" :limits="videoLimits" @saved="refreshStatus"></SettingsForm>
		</v-col>
	</v-row>
</template>
