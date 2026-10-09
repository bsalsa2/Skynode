// ---------------------------------------------------------------------------
//  PHONE UPLOAD PAGE SETTINGS
//
//  CLIENT_ID is the "OAuth client ID" you create in the Google Cloud console
//  (the steps are in web/README.md, under "Phone upload page"). It looks like
//  1234567890-abcdefg.apps.googleusercontent.com.
//
//  It is NOT a secret: Google designed it to sit in a web page. What protects
//  your Drive is that only people you list as test users can sign in, and that
//  the page asks only for the narrow drive.file permission. Never paste a
//  "client secret" or an API key here.
// ---------------------------------------------------------------------------

export const CLIENT_ID = ''; // TODO: paste your OAuth client ID
