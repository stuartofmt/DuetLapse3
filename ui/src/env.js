// Where the page is running: ?theme / ?mobile are added by the DWC plugin page, which shows this page in an iframe.
export const query = new URLSearchParams(window.location.search);
export const embedded = window.parent !== window;
export const PLUGIN = "duetLapse3"; // The source name in messages to and from the DWC plugin page
