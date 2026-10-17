<!-- Config tab: the settings in duetLapse3.json that are not on the Cameras or Video tabs -->
<script setup>
import SettingsForm from "../components/SettingsForm.vue";
</script>

<template>
	<v-row justify="center">
		<v-col cols="12" md="10" lg="8">
			<v-alert type="info" variant="tonal" density="compact" class="mb-4">
				Changes here take effect when duetLapse3 is restarted.
			</v-alert>
			<SettingsForm tab="config" save-url="/config/save"></SettingsForm>
		</v-col>
	</v-row>
</template>
