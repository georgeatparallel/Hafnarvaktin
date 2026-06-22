# Sundahöfn Spotter

The Expo (React Native) app for the EK RN exam. Three read-only tabs over the
Hafnarvaktin backend — the wider project story lives in the parent `rn/` and the
repo-root READMEs, so this file is just the basics.

## What it does

* **Harbour** — both Sundahöfn cameras (N + S) with server-drawn YOLO boxes,
  refreshed ~every 1.5 s.
* **Fleet** — vessels *In port* / *At sea* from the Samgöngustofa registry
  mirror; pull-to-refresh re-fetches.
* **Chat** — POSTs to the AI exam's n8n webhook (`CHAT_URL`); the NanoClaw agent
  answers using live harbour data.

Plus a Firebase email/password login gate.

## Stack

| layer | library |
|---|---|
| runtime | Expo SDK 54 |
| navigation | `@react-navigation/native` + `bottom-tabs` |
| auth | Firebase Auth (email/password) |
| live frames | `<Image>` polling the backend snapshot endpoint |
| fleet list | `ScrollView` + `fetch` with pull-to-refresh |
| chat | `fetch` POST to the n8n webhook (`CHAT_URL`) |
| persistence | `@react-native-async-storage/async-storage` |

## Files

```
sundahofn-spotter/
├── App.js                auth gate + bottom-tab navigator
├── firebaseConfig.js     Firebase init (auth only)
├── index.js              Expo entry point
├── app.json              Expo config
├── lib/api.js            BACKEND_URL + CHAT_URL
├── components/icons/     bottom-tab icons
└── screens/
    ├── LoginScreen.js    email + password sign-in/sign-up
    ├── LiveScreen.js     two cameras, ~1.5s polling
    ├── VesselsScreen.js  fleet SectionList, in-port vs at-sea
    └── ChatScreen.js     chat via the n8n webhook
```

## Setup & run

```bash
npm install
npx expo start        # open in Expo Go on an iPhone
```

`firebaseConfig.js` holds the Firebase Auth project config (email/password only —
no Firestore or Storage). The Chat tab uses the already-live n8n webhook, so no
backend key or local agent setup is needed.
