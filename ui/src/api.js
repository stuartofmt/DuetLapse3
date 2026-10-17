// Calls to duetLapse3. get / postJson return the parsed JSON (or null); getText returns the reply as text.
// On an error they throw an Error whose message is the server's text; error.status and error.data hold
// the HTTP status and the parsed reply (e.g. { errors: { setting: message } } when a save is refused).

async function request(url, options, asText = false) {
	const response = await fetch(url, options);
	const text = await response.text();
	let data = null;
	try {
		data = text ? JSON.parse(text) : null;
	} catch {
		// Not JSON
	}
	if (!response.ok) {
		const error = new Error(data?.message || data?.detail || text || response.statusText || `HTTP ${response.status}`);
		error.status = response.status;
		error.data = data;
		throw error;
	}
	return asText ? text : data;
}

export const api = {
	get: (url) => request(url),
	getText: (url) => request(url, undefined, true),
	postJson: (url, body) => request(url, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	}),
};

// The url of a file on the computer running duetLapse3 (images, videos, logs)
export const fileUrl = (path) => "/getfile?path=" + encodeURIComponent(path);
