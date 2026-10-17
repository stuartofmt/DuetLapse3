# duetLapse3 web interface

The duetLapse3 page (Status, Controls, Video, Files, Info, Cameras and Config tabs), written as Vue 3 single-file components with Vuetify 4 and built with Vite. It's the same setup as duetPrintGuard's `ui/`, so it has the DWC 3.7 look and follows DWC's light / dark theme when shown inside DWC.

`npm run build` writes the page and its assets to `Code/dsf/static/app/`, which duetLapse3 serves at `/`. The built files are committed, so the plugin needs no Node.js or internet access. **After changing anything in `ui/`, run `npm run build` and commit `Code/dsf/static/app/` with the change.**

## Building

```bash
cd ui
npm install      # once
npm run build    # writes Code/dsf/static/app
```

## Developing with live reload

Start duetLapse3 (the plugin, or `python duetLapse3.py <folder>`), then:

```bash
npm run dev
```

and open <http://localhost:5173/static/app/index.html>. Changes show as soon as they are saved. API calls, images and files go to the running duetLapse3: `http://localhost:17800` unless `DUETLAPSE3_URL` says otherwise, e.g. `DUETLAPSE3_URL=http://192.168.1.20:17800 npm run dev`.

`?tab=<name>` opens a tab directly, e.g. `?tab=files`. `?theme=dark` or `?theme=light` picks the theme (the DWC plugin page adds it).

## Layout

| File | Purpose |
| --- | --- |
| `index.html`, `src/main.js` | The page |
| `src/App.vue` | The tab bar, the shown tab, the message bar and the confirm dialog |
| `src/tabs/` | One component per tab |
| `src/components/SettingsForm.vue` | The settings cards used by the Video and Config tabs |
| `src/vuetify.js` | Vuetify set up as DWC 3.7 does, and following DWC's theme when shown inside DWC |
| `src/status.js` | `/api/status`, read every 3 seconds while the page is visible, for every tab |
| `src/visibility.js` | Whether the page is being shown, so it stops polling while hidden |
| `src/api.js`, `src/notify.js`, `src/env.js` | Server calls, messages and confirm, and where the page is running |
| `src/icons.js` | The icons used. Only these are bundled; import new ones from `@mdi/js` here |
| `src/app.css`, `src/fonts/` | Shared styles and the Roboto font DWC uses |

## Server routes the page uses

| Route | What it returns or does |
| --- | --- |
| `GET /api/status` | duetLapse3 and printer state, frames, layer, last image, which commands are allowed |
| `GET /api/info` | The page address, files and folders, and the settings in use |
| `GET /api/files?path=` | A folder's files and what can be done with each (blank = the top folder) |
| `GET /api/settings?tab=config\|video` | The settings for that tab, with type, choices and help |
| `GET /api/cameras` | The camera urls |
| `POST /config/save`, `/video/save`, `/cameras/save` | Check and save settings. 400 with `{errors: {setting: message}}` if any are invalid |
| `GET /command/<name>`, `/terminate/<type>`, `/snapshot`, `/makevideo`, `/zip`, `/delete`, `/getfile`, `/camera/preview` | Actions |
