<!-- Files tab: the images, videos and zip files, with download, video, zip and delete -->
<script setup>
import { computed, onMounted, ref } from "vue";
import { api, fileUrl } from "../api.js";
import { confirm, notify } from "../notify.js";
import { mdiArrowUp, mdiDelete, mdiDownload, mdiFile, mdiFolder, mdiFolderZip, mdiMovieOpen, mdiRefresh } from "../icons.js";

function savedPath() {
	try {
		return sessionStorage.getItem("duetLapse3.path") || "";
	} catch {
		return "";
	}
}

const listing = ref(null);
const loading = ref(false);
const busy = ref("");

// The folder being shown, relative to the top folder
const where = computed(() => {
	if (!listing.value) return "";
	const { path, top } = listing.value;
	return path.startsWith(top) ? path.slice(top.length).replace(/^[/\\]/, "") : path;
});

async function open(path) {
	loading.value = true;
	try {
		listing.value = await api.get(`/api/files?path=${encodeURIComponent(path)}`);
		try {
			sessionStorage.setItem("duetLapse3.path", path);
		} catch {
			// Not remembered
		}
	} catch (err) {
		if (path !== "") {
			return open(""); // The folder has gone - show the top folder
		}
		notify(`Could not list the files: ${err.message}`, "error", 6000);
	} finally {
		loading.value = false;
	}
}

const refresh = () => open(listing.value?.path ?? "");

async function action(entry, kind) {
	if (kind === "delete" && !await confirm(`Delete ${entry.name}?`, { title: "Delete", color: "error" })) {
		return;
	}
	busy.value = entry.path + kind;
	try {
		if (kind === "video") {
			const result = await api.getText(`/makevideo?path=${encodeURIComponent(entry.path)}&xtratime=false`);
			notify(result.trim() || "Done", result.toLowerCase().includes("error") ? "error" : "success", 8000);
		} else {
			await api.getText(`/${kind}?path=${encodeURIComponent(entry.path)}`);
			notify(kind === "zip" ? `${entry.name} zipped` : `${entry.name} deleted`);
		}
	} catch (err) {
		notify(`${kind} failed: ${err.message}`, "error", 6000);
	} finally {
		busy.value = "";
		refresh();
	}
}

function size(bytes) {
	if (bytes === null) return "";
	const units = ["B", "KB", "MB", "GB"];
	let i = 0;
	while (bytes >= 1024 && i < units.length - 1) {
		bytes /= 1024;
		i++;
	}
	return `${bytes.toFixed(i ? 1 : 0)} ${units[i]}`;
}

const modified = (seconds) => new Date(seconds * 1000).toLocaleString();

onMounted(() => open(savedPath()));
</script>

<template>
	<v-card>
		<v-card-title class="d-flex align-center flex-wrap ga-2">
			Files
			<v-spacer></v-spacer>
			<v-btn v-if="listing?.parent" :prepend-icon="mdiArrowUp" variant="text" size="small" @click="open(listing.parent)">Up</v-btn>
			<v-btn :prepend-icon="mdiRefresh" variant="text" size="small" :loading="loading" @click="refresh">Refresh</v-btn>
		</v-card-title>
		<v-card-subtitle v-if="listing" class="dl3-break">{{ where ? `${where}` : listing.top }}</v-card-subtitle>
		<v-table density="compact" hover>
			<thead>
				<tr>
					<th>Name</th>
					<th class="d-none d-sm-table-cell">Modified</th>
					<th class="d-none d-sm-table-cell text-end">Size</th>
					<th class="text-end">Actions</th>
				</tr>
			</thead>
			<tbody>
				<tr v-if="listing && !listing.entries.length">
					<td colspan="4" class="text-medium-emphasis">No files yet</td>
				</tr>
				<tr v-for="entry in listing?.entries ?? []" :key="entry.path">
					<td class="dl3-break">
						<a v-if="entry.isDir" href="#" class="text-primary text-decoration-none" @click.prevent="open(entry.path)">
							<v-icon :icon="mdiFolder" size="small" class="me-1"></v-icon>{{ entry.name }}
						</a>
						<a v-else :href="fileUrl(entry.path)" target="_blank" class="text-primary text-decoration-none">
							<v-icon :icon="mdiFile" size="small" class="me-1"></v-icon>{{ entry.name }}
						</a>
					</td>
					<td class="d-none d-sm-table-cell text-no-wrap">{{ modified(entry.modified) }}</td>
					<td class="d-none d-sm-table-cell text-end text-no-wrap">{{ size(entry.size) }}</td>
					<td class="text-end text-no-wrap">
						<v-btn v-if="!entry.isDir" :icon="mdiDownload" :href="fileUrl(entry.path)" target="_blank"
							   variant="text" size="small" title="Download"></v-btn>
						<v-btn v-if="entry.canVideo" :icon="mdiMovieOpen" variant="text" size="small" color="success" title="Make a video"
							   :loading="busy === entry.path + 'video'" @click="action(entry, 'video')"></v-btn>
						<v-btn v-if="entry.canZip" :icon="mdiFolderZip" variant="text" size="small" color="warning" title="Zip"
							   :loading="busy === entry.path + 'zip'" @click="action(entry, 'zip')"></v-btn>
						<v-btn v-if="entry.canDelete" :icon="mdiDelete" variant="text" size="small" color="error" title="Delete"
							   :loading="busy === entry.path + 'delete'" @click="action(entry, 'delete')"></v-btn>
					</td>
				</tr>
			</tbody>
		</v-table>
	</v-card>
</template>
