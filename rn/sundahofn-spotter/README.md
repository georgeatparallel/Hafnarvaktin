# Sundahöfn Spotter

A small React Native (Expo) app that consumes the **Hafnarvaktin** harbour-watch
stack on Helmut. It is the EK React Native exam project and runs on the same
backend as the ML and AI tracks, so the three exams share one live stack.

## What it does

Three read-only tabs. **Harbour** and **Fleet** consume the same Spring Boot
backend that the ML and AI exam projects use; **Chat** calls the AI exam's n8n
webhook:

* **Harbour** — both Sundahöfn cameras (N and S) with YOLO detection boxes drawn
  server-side. Refreshes every 1.5 seconds via a cache-buster query param.
* **Fleet** — vessels currently *In port* and *At sea*, drawn from the
  Samgöngustofa registry mirror (Westfjords-home-ported boats). One fetch
  on first visit, cached in memory so switching tabs doesn't re-spinner;
  pull-to-refresh forces a re-fetch.
* **Chat** — ask the harbour assistant about what's been spotted. The app POSTs
  your message to the AI exam's n8n webhook (`CHAT_URL`), which runs the NanoClaw
  agent (MCP tools + RAG over the live harbour data) and returns the reply.

Plus a Firebase email/password login gate so the app starts in a familiar
authenticated state.

## Stack (matches semester material)

| layer | library |
|---|---|
| runtime | Expo SDK 54 |
| navigation | `@react-navigation/native` + `@react-navigation/bottom-tabs` |
| auth | Firebase Auth (email/password) |
| live frames | plain `<Image>` polling the backend snapshot endpoint |
| fleet list | `SectionList` + `fetch` with pull-to-refresh + module-level cache |
| chat | `fetch` POST to the AI exam's n8n webhook (`CHAT_URL`); the n8n workflow runs the NanoClaw agent |
| persistence | `@react-native-async-storage/async-storage` (so the login survives restarts) |

## Files

```
sundahofn-spotter/
├── App.js                      auth gate + bottom-tab navigator
├── firebaseConfig.js           Firebase init (auth only — no Firestore/Storage)
├── index.js                    Expo entry point
├── app.json                    Expo project config
├── package.json
├── lib/
│   └── api.js                  BACKEND_URL (Spring Boot) + CHAT_URL (n8n webhook)
├── components/
│   └── icons/                  bottom-tab icons (harbour / fleet / chat)
└── screens/
    ├── LoginScreen.js          email + password + sign-in/sign-up
    ├── LiveScreen.js           two cameras, server-annotated snapshots, ~1.5s polling
    ├── VesselsScreen.js        SectionList of Samgöngustofa fleet, in-port vs at-sea
    └── ChatScreen.js           chat with the Hafnarvaktin assistant (via n8n webhook)
```

## How it talks to Hafnarvaktin

```
RN app
  ├── GET  http://159.195.148.91:8191/api/v1/cameras/9/snapshot   → JPEG (N)
  ├── GET  http://159.195.148.91:8191/api/v1/cameras/6/snapshot   → JPEG (S)
  ├── GET  http://159.195.148.91:8191/api/v1/vessels/status       → { inPort, atSea }
  └── POST https://n8n.syntaxerror.is/webhook/chat                → { reply }
                                                                       │
                                            n8n workflow runs the      │
                                            NanoClaw agent (MCP +      │
                                            RAG over harbour data)     │
                                            and returns the reply ─────┘
```

Same backend as the ML exam (boat detector) and the AI exam (NanoClaw +
Telegram bot). The unified-stack story is the whole point of choosing
Hafnarvaktin as the joint exam project.

## Setup

1. `npm install`
2. `firebaseConfig.js` holds the Firebase Auth project config (email/password
   sign-in only — no Firestore or Storage).
3. `npx expo start` — open in Expo Go on your iPhone.

The Chat tab talks to the AI exam's n8n webhook (`CHAT_URL` in `lib/api.js`),
which is already live — no backend key or local agent setup is needed for the
RN app.

## Exam walkthrough

* Live demo on my phone:
  * Sign in → land on **Harbour** → both cameras updating in near-real-time with
    YOLO boxes drawn on the harbour scene.
  * Swap to **Fleet** → see Sundahöfn regulars from Samgöngustofa split into
    "In port" and "At sea"; pull-to-refresh re-fetches.
  * Swap to **Chat** → ask "how many boats today?" → assistant answers using
    the live detection feed as context.
* Code walk-through file by file:
  * `App.js` — `onAuthStateChanged` decides Login vs Tabs; bottom-tab navigator.
  * `LoginScreen.js` — two Firebase Auth methods, one form.
  * `LiveScreen.js` — `useState` + `useEffect` + `setInterval` to swap an
    `<Image>` URI every 1.5s; server-side boxes mean the client is dumb-simple.
  * `VesselsScreen.js` — `SectionList` + `fetch` + `RefreshControl`; a
    module-level `cache` variable keeps the last response in memory so
    switching tabs doesn't re-fetch.
  * `ChatScreen.js` — message array in `useState`, POST history on send, append
    assistant reply on response.
  * `lib/api.js` — one shared backend URL.
* Backend extension (Java) — `is.fljotavik.backend.vessels.VesselsController`:
  a `JdbcTemplate` query against the Samgöngustofa-backed `vessels` table that
  splits results into In-port / At-sea, with a Datalastic live-AIS path and a
  registry fallback. The Chat tab needs no backend code — it calls the AI
  exam's n8n webhook directly.
