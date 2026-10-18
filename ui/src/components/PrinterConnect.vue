<!-- Shown on every tab while the printer is not connected: why, and the printer settings to change it (address, port, password) -->
<script setup>
import { computed, reactive, ref, watch } from "vue";
import { api } from "../api.js";
import { notify } from "../notify.js";
import { serverText, t } from "../i18n.js";
import { refreshStatus, status } from "../status.js";
import { mdiEye, mdiEyeOff, mdiRefresh } from "../icons.js";

const s = computed(() => status.data);
const shown = computed(() => s.value && !s.value.connected);
const form = reactive({ duet_ip: "", duet_port: "", duet_password: "" });  // Setting names
const errors = ref({});
const busy = ref(false);
const showPassword = ref(false);

// Filled in each time the printer is lost - not while it is being edited
watch(shown, (value) => {
	if (value) {
		form.duet_ip = s.value.duet || "";
		form.duet_port = String(s.value.duetport ?? "");
		form.duet_password = "";
		errors.value = {};
	}
}, { immediate: true });

async function connect() {
	busy.value = true;
	errors.value = {};
	try {
		const reply = await api.postJson("/printer/connect", { ...form });
		notify(serverText(reply.message, reply.messageCode), "success");
		form.duet_password = "";
		await refreshStatus();
	} catch (err) {
		const errs = err.data?.errors || {};
		errors.value = Object.fromEntries(Object.entries(errs).map(([key, text]) => [key, serverText(text, err.data.errorCodes?.[key])]));
		notify(errors.value[""] || serverText(err.message, err.data?.messageCode), "error", 6000);
	} finally {
		busy.value = false;
	}
}
</script>

<template>
	<v-alert v-if="shown" :type="s.connectError ? 'error' : 'warning'" variant="tonal" class="mb-4">
		<div class="mb-1"><strong>{{ s.connectError ? serverText(s.connectError, s.connectErrorCode) : t("printer.cannotConnect", { printer: s.printer }) }}</strong></div>
		<div class="text-body-2 mb-3">
			{{ s.connectError ? t("printer.noMoreTries") : t("printer.keepsTrying") }}
			{{ t("printer.saved") }}
		</div>
		<v-form class="d-flex flex-wrap ga-3 align-start" @submit.prevent="connect">
			<v-text-field v-model="form.duet_ip" :label="t('printer.address')" :hint="t('printer.addressHint')" persistent-hint
						  density="compact" variant="outlined" style="min-width: 200px; flex: 2 1 200px"
						  :error-messages="errors.duet_ip"></v-text-field>
			<v-text-field v-model="form.duet_port" :label="t('printer.port')" :hint="t('printer.portHint')" persistent-hint type="number"
						  density="compact" variant="outlined" style="min-width: 100px; flex: 1 1 100px"
						  :error-messages="errors.duet_port"></v-text-field>
			<v-text-field v-model="form.duet_password" :label="t('printer.password')" :hint="t('printer.passwordHint')" persistent-hint
						  :type="showPassword ? 'text' : 'password'" :append-inner-icon="showPassword ? mdiEyeOff : mdiEye"
						  autocomplete="off" density="compact" variant="outlined" style="min-width: 180px; flex: 2 1 180px"
						  :error-messages="errors.duet_password" @click:append-inner="showPassword = !showPassword"></v-text-field>
			<v-btn type="submit" color="primary" variant="flat" :prepend-icon="mdiRefresh" :loading="busy">{{ t("printer.connect") }}</v-btn>
		</v-form>
	</v-alert>
</template>
