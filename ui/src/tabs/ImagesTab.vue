<!--
	Images tab: a file browser for the images, videos and zip files - breadcrumb path, list or grid (with thumbnails),
	search and sort. Images and videos open in a viewer; each item's actions are in its menu.
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api, fileUrl } from "../api.js";
import { clearNotify, confirm, notify } from "../notify.js";
import { requestVideo } from "../videos.js";
import { changes, status } from "../status.js";
import { language, t } from "../i18n.js";
import {
	mdiChevronLeft, mdiChevronRight, mdiClose, mdiDelete, mdiDotsVertical, mdiDownload, mdiFileDocumentOutline, mdiFileVideo,
	mdiFolder, mdiFolderImage, mdiFolderZip, mdiHome, mdiImage, mdiMagnify, mdiMovieOpen, mdiOpenInNew, mdiRefresh, mdiSort,
	mdiViewGrid, mdiViewList,
} from "../icons.js";

const PAGE = 60; // Items shown at first - "Show more" adds more (image folders can hold thousands)

// Remembered between visits (per browser tab for the folder, per browser for the view and sort)
function remembered(store, key, fallback) {
	try {
		return store.getItem(key) ?? fallback;
	} catch {
		return fallback;
	}
}
function remember(store, key, value) {
	try {
		store.setItem(key, value);
	} catch {
		// Not remembered
	}
}

const listing = ref(null);
const loading = ref(false);
const busy = ref("");
const search = ref("");
const view = ref(remembered(localStorage, "duetLapse3.view", "list"));
const sort = ref(remembered(localStorage, "duetLapse3.sort", "newest"));
const shown = ref(PAGE);
const viewer = ref(null); // The image or video being shown
watch(view, (v) => remember(localStorage, "duetLapse3.view", v));
watch(sort, (v) => remember(localStorage, "duetLapse3.sort", v));

const sorts = [
	{ title: t("images.newest"), value: "newest" },
	{ title: t("images.oldest"), value: "oldest" },
	{ title: t("images.name"), value: "name" },
	{ title: t("images.size"), value: "size" },
];

const kinds = {
	folder: { icon: mdiFolder, color: "primary" },
	image: { icon: mdiImage, color: "teal" },
	video: { icon: mdiFileVideo, color: "deep-purple" },
	zip: { icon: mdiFolderZip, color: "amber-darken-2" },
	log: { icon: mdiFileDocumentOutline, color: "grey" },
	file: { icon: mdiFileDocumentOutline, color: "grey" },
};
const kindOf = (entry) => kinds[entry.kind] ?? kinds.file;
const folderIcon = (entry) => (entry.images ? mdiFolderImage : mdiFolder);

// The breadcrumb: the top folder, then each folder below it
const crumbs = computed(() => {
	if (!listing.value) return [];
	const { path, top } = listing.value;
	const sep = top.includes("\\") && !top.includes("/") ? "\\" : "/";
	const below = path.startsWith(top) ? path.slice(top.length).split(/[\\/]/).filter(Boolean) : [];
	const list = [{ title: t("images.top"), path: top }];
	let current = top;
	for (const part of below) {
		current = current.replace(/[\\/]$/, "") + sep + part;
		list.push({ title: part, path: current });
	}
	return list;
});

const entries = computed(() => {
	const all = listing.value?.entries ?? [];
	const text = search.value.trim().toLowerCase();
	const found = text ? all.filter((e) => e.name.toLowerCase().includes(text)) : [...all];
	const byName = (a, b) => a.name.localeCompare(b.name, undefined, { numeric: true });
	const order = {
		newest: (a, b) => b.modified - a.modified,
		oldest: (a, b) => a.modified - b.modified,
		name: byName,
		size: (a, b) => (b.size ?? -1) - (a.size ?? -1) || byName(a, b),
	}[sort.value];
	// Folders first, then files
	return found.sort((a, b) => (b.isDir - a.isDir) || order(a, b));
});
const visible = computed(() => entries.value.slice(0, shown.value));
const images = computed(() => entries.value.filter((e) => e.kind === "image"));

async function open(path) {
	loading.value = true;
	try {
		listing.value = await api.get(`/api/files?path=${encodeURIComponent(path)}`);
		remember(sessionStorage, "duetLapse3.path", path);
		shown.value = PAGE;
		search.value = "";
	} catch (err) {
		if (path !== "") {
			return open(""); // The folder has gone - show the top folder
		}
		notify(t("images.couldNotList", { error: err.message }), "error", 6000);
	} finally {
		loading.value = false;
	}
}

const refresh = () => open(listing.value?.path ?? "");

// Refresh by itself when something shown here may have changed - images captured, a video made, files deleted or zipped -
// at most every RELOAD ms, keeping the search and how much is shown
const RELOAD = 5000;
const changed = computed(() => [status.data?.frames, status.data?.frames2, status.data?.videoEvents?.at(-1)?.seq, status.data?.run, changes.files].join());
let lastReload = 0;
let pending = null;
watch(changed, () => {
	if (pending === null) {
		pending = setTimeout(reload, Math.max(0, lastReload + RELOAD - Date.now()));
	}
});
onBeforeUnmount(() => clearTimeout(pending));

async function reload() {
	pending = null;
	lastReload = Date.now();
	if (!listing.value || loading.value || busy.value) {
		return;  // Refreshed anyway when that finishes
	}
	try {
		listing.value = await api.get(`/api/files?path=${encodeURIComponent(listing.value.path)}`);
	} catch {
		open("");  // The folder has gone - show the top folder
	}
}

// Clicking an item: open a folder, view an image or video, otherwise download it
function select(entry) {
	if (entry.isDir) {
		open(entry.path);
	} else if (entry.kind === "image" || entry.kind === "video") {
		viewer.value = entry;
	} else {
		window.open(fileUrl(entry.path), "_blank");
	}
}

// Previous / next image in the viewer
function step(by) {
	const list = images.value;
	const i = list.findIndex((e) => e.path === viewer.value?.path);
	if (i >= 0 && list.length) {
		viewer.value = list[(i + by + list.length) % list.length];
	}
}

async function action(entry, kind) {
	const question = t("images.deleteConfirm", { name: entry.name }) + (entry.isDir ? `\n${t("images.deleteFolder", { contents: contents(entry) })}` : "");
	if (kind === "delete" && !await confirm(question, { title: t("images.deleteTitle"), color: "error" })) {
		return;
	}
	busy.value = entry.path;
	try {
		if (kind === "video") {
			notify(t("images.making", { name: entry.name }), "info", 60000);
			await requestVideo(`/makevideo?path=${encodeURIComponent(entry.path)}&xtratime=false`);  // The result is announced
			clearNotify();  // The "Making" message
		} else {
			await api.getText(`/${kind}?path=${encodeURIComponent(entry.path)}`);
			notify(t(kind === "zip" ? "images.zipped" : "images.deleted", { name: entry.name }));
		}
	} catch (err) {
		notify(t("images.failed", { action: t({ video: "images.makeVideo", zip: "images.zip", delete: "images.delete" }[kind]), error: err.message }), "error", 6000);
	} finally {
		busy.value = "";
		refresh();
	}
}

function size(bytes) {
	if (bytes === null || bytes === undefined) return "";
	const units = ["B", "KB", "MB", "GB"];
	let i = 0;
	while (bytes >= 1024 && i < units.length - 1) {
		bytes /= 1024;
		i++;
	}
	return `${bytes.toFixed(i ? 1 : 0)} ${units[i]}`;
}

const when = (seconds) => new Date(seconds * 1000).toLocaleString(language);
// What a folder holds, e.g. "40 images, 2 videos"
const contents = (entry) => [entry.images ? t("images.imageCount", { n: entry.images }) : "", entry.videos ? t("images.videoCount", { n: entry.videos }) : ""]
	.filter(Boolean).join(", ") || t("images.folder");
const details = (entry) => entry.isDir ? `${contents(entry)} · ${when(entry.modified)}` : `${size(entry.size)} · ${when(entry.modified)}`;

onMounted(() => open(remembered(sessionStorage, "duetLapse3.path", "")));
</script>

<template>
	<v-card>
		<!-- Path and tools -->
		<v-toolbar density="comfortable" color="transparent" class="px-2 flex-wrap">
			<v-breadcrumbs :items="crumbs" density="compact" class="pa-0 flex-grow-1 dl3-break">
				<template #prepend>
					<v-icon :icon="mdiHome" size="small" class="me-1"></v-icon>
				</template>
				<template #item="{ item, index }">
					<v-breadcrumbs-item :disabled="index === crumbs.length - 1" class="dl3-crumb" @click="open(item.path)">
						{{ item.title }}
					</v-breadcrumbs-item>
				</template>
				<template #divider>
					<v-icon :icon="mdiChevronRight" size="small"></v-icon>
				</template>
			</v-breadcrumbs>
			<v-btn :icon="mdiRefresh" variant="text" size="small" :loading="loading" :title="t('common.refresh')" @click="refresh"></v-btn>
		</v-toolbar>
		<div class="d-flex flex-wrap align-center ga-2 px-4 pb-2">
			<v-text-field v-model="search" :prepend-inner-icon="mdiMagnify" :placeholder="t('images.search')" clearable
						  variant="outlined" density="compact" hide-details style="min-width: 180px; max-width: 320px"
						  @update:model-value="shown = PAGE"></v-text-field>
			<v-spacer></v-spacer>
			<v-menu>
				<template #activator="{ props }">
					<v-btn v-bind="props" :prepend-icon="mdiSort" variant="text" size="small">
						{{ sorts.find((s) => s.value === sort).title }}
					</v-btn>
				</template>
				<v-list density="compact">
					<v-list-item v-for="s in sorts" :key="s.value" :title="s.title" :active="s.value === sort" @click="sort = s.value"></v-list-item>
				</v-list>
			</v-menu>
			<v-btn-toggle v-model="view" mandatory density="compact" variant="outlined" divided>
				<v-btn value="list" :icon="mdiViewList" :title="t('images.list')"></v-btn>
				<v-btn value="grid" :icon="mdiViewGrid" :title="t('images.grid')"></v-btn>
			</v-btn-toggle>
		</div>
		<v-divider></v-divider>

		<!-- Nothing here -->
		<div v-if="listing && !entries.length" class="text-center text-medium-emphasis pa-8">
			<v-icon :icon="search ? mdiMagnify : mdiFolder" size="48" class="mb-2"></v-icon>
			<div>{{ search ? t("images.noMatch", { search }) : t("images.empty") }}</div>
		</div>

		<!-- List -->
		<v-list v-else-if="view === 'list'" lines="two" class="py-0">
			<v-list-item v-for="entry in visible" :key="entry.path" :title="entry.name" :subtitle="details(entry)" @click="select(entry)">
				<template #prepend>
					<v-avatar rounded="sm" size="48" :color="entry.thumbnail ? undefined : kindOf(entry).color" variant="tonal" class="me-2">
						<img v-if="entry.thumbnail" :src="fileUrl(entry.thumbnail)" loading="lazy" alt="" class="dl3-thumb">
						<v-icon v-else :icon="entry.isDir ? folderIcon(entry) : kindOf(entry).icon"></v-icon>
					</v-avatar>
				</template>
				<template #append>
					<v-progress-circular v-if="busy === entry.path" indeterminate size="20" width="2" class="me-2"></v-progress-circular>
					<v-menu location="bottom end">
						<template #activator="{ props }">
							<v-btn v-bind="props" :icon="mdiDotsVertical" variant="text" size="small" @click.stop></v-btn>
						</template>
						<v-list density="compact">
							<v-list-item v-if="!entry.isDir" :prepend-icon="mdiOpenInNew" :title="t('images.openTab')" :href="fileUrl(entry.path)" target="_blank"></v-list-item>
							<v-list-item v-if="!entry.isDir" :prepend-icon="mdiDownload" :title="t('common.download')" :href="fileUrl(entry.path)" :download="entry.name"></v-list-item>
							<v-list-item v-if="entry.canVideo" :prepend-icon="mdiMovieOpen" :title="t('images.makeVideo')" @click="action(entry, 'video')"></v-list-item>
							<v-list-item v-if="entry.canZip" :prepend-icon="mdiFolderZip" :title="t('images.zip')" @click="action(entry, 'zip')"></v-list-item>
							<v-list-item v-if="entry.canDelete" :prepend-icon="mdiDelete" :title="t('images.delete')" base-color="error" @click="action(entry, 'delete')"></v-list-item>
							<v-list-item v-if="entry.isDir && !entry.canDelete" :title="t('images.inUse')" disabled></v-list-item>
						</v-list>
					</v-menu>
				</template>
			</v-list-item>
		</v-list>

		<!-- Grid -->
		<v-container v-else fluid class="pa-3">
			<v-row dense>
				<v-col v-for="entry in visible" :key="entry.path" cols="6" sm="4" md="3" lg="2">
					<v-card variant="outlined" class="h-100" @click="select(entry)">
						<div class="dl3-tile">
							<img v-if="entry.thumbnail" :src="fileUrl(entry.thumbnail)" loading="lazy" alt="">
							<v-icon v-else :icon="entry.isDir ? folderIcon(entry) : kindOf(entry).icon" :color="kindOf(entry).color" size="48"></v-icon>
						</div>
						<div class="d-flex align-center">
							<div class="pa-2 flex-grow-1" style="min-width: 0">
								<div class="text-body-2 font-weight-medium text-truncate" :title="entry.name">{{ entry.name }}</div>
								<div class="text-caption text-medium-emphasis text-truncate">
									{{ entry.isDir ? contents(entry) : size(entry.size) }}
								</div>
							</div>
							<v-progress-circular v-if="busy === entry.path" indeterminate size="18" width="2" class="me-1"></v-progress-circular>
							<v-menu v-if="entry.canDelete || !entry.isDir" location="bottom end">
								<template #activator="{ props }">
									<v-btn v-bind="props" :icon="mdiDotsVertical" variant="text" size="small" @click.stop></v-btn>
								</template>
								<v-list density="compact">
									<v-list-item v-if="!entry.isDir" :prepend-icon="mdiDownload" :title="t('common.download')" :href="fileUrl(entry.path)" :download="entry.name"></v-list-item>
									<v-list-item v-if="entry.canVideo" :prepend-icon="mdiMovieOpen" :title="t('images.makeVideo')" @click="action(entry, 'video')"></v-list-item>
									<v-list-item v-if="entry.canZip" :prepend-icon="mdiFolderZip" :title="t('images.zip')" @click="action(entry, 'zip')"></v-list-item>
									<v-list-item v-if="entry.canDelete" :prepend-icon="mdiDelete" :title="t('images.delete')" base-color="error" @click="action(entry, 'delete')"></v-list-item>
								</v-list>
							</v-menu>
						</div>
					</v-card>
				</v-col>
			</v-row>
		</v-container>

		<div v-if="entries.length > shown" class="text-center pa-3">
			<v-btn variant="tonal" @click="shown += PAGE">{{ t("images.more", { n: Math.min(PAGE, entries.length - shown), total: entries.length - shown }) }}</v-btn>
		</div>
	</v-card>

	<!-- Image / video viewer -->
	<v-dialog :model-value="!!viewer" max-width="1100" @update:model-value="viewer = null">
		<v-card v-if="viewer">
			<v-toolbar density="compact" color="transparent">
				<v-toolbar-title class="text-body-1">{{ viewer.name }}</v-toolbar-title>
				<v-btn :icon="mdiDownload" :href="fileUrl(viewer.path)" :download="viewer.name" :title="t('common.download')"></v-btn>
				<v-btn :icon="mdiClose" :title="t('common.close')" @click="viewer = null"></v-btn>
			</v-toolbar>
			<div class="dl3-viewer" @keydown.left="step(-1)" @keydown.right="step(1)" tabindex="0">
				<video v-if="viewer.kind === 'video'" :src="fileUrl(viewer.path)" controls autoplay></video>
				<img v-else :src="fileUrl(viewer.path)" :alt="viewer.name">
				<template v-if="viewer.kind === 'image' && images.length > 1">
					<v-btn :icon="mdiChevronLeft" class="dl3-viewer-prev" variant="tonal" @click="step(-1)"></v-btn>
					<v-btn :icon="mdiChevronRight" class="dl3-viewer-next" variant="tonal" @click="step(1)"></v-btn>
				</template>
			</div>
			<v-card-subtitle class="py-2">{{ details(viewer) }}</v-card-subtitle>
		</v-card>
	</v-dialog>
</template>

<style scoped>
.dl3-thumb {
	width: 100%;
	height: 100%;
	object-fit: cover;
}
.dl3-tile {
	aspect-ratio: 4 / 3;
	display: flex;
	align-items: center;
	justify-content: center;
	background: rgba(var(--v-theme-on-surface), 0.05);
	overflow: hidden;
}
.dl3-tile img {
	width: 100%;
	height: 100%;
	object-fit: cover;
}
.dl3-crumb {
	cursor: pointer;
}
.dl3-viewer {
	position: relative;
	background: #000;
	display: flex;
	justify-content: center;
	outline: none;
}
.dl3-viewer img,
.dl3-viewer video {
	max-width: 100%;
	max-height: 75vh;
	display: block;
}
.dl3-viewer-prev,
.dl3-viewer-next {
	position: absolute;
	top: 50%;
	transform: translateY(-50%);
}
.dl3-viewer-prev {
	left: 8px;
}
.dl3-viewer-next {
	right: 8px;
}
</style>
