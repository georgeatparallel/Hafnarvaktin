# `rn/` — React Native exam track

The app lives in [`sundahofn-spotter/`](sundahofn-spotter/) — an Expo (React Native) app built as the EK React Native exam project.

## Three tabs

| tab | purpose | backend |
|---|---|---|
| **Harbour** | both Sundahöfn cameras (N=9, S=6) with server-drawn YOLO boxes, polled every ~1.5 s | `poc/backend` snapshot endpoints |
| **Fleet** | Samgöngustofa-backed vessel list split into *In port* / *At sea*; each card shows the skipaskrárnúmer with a deep link to the vessel's mbl.is skipaskrá page, plus live speed for boats at sea | `poc/backend` `/api/v1/vessels/status` |
| **Chat** | ask the harbour assistant about what's been spotted | n8n webhook (`/webhook/chat`) → the AI exam's NanoClaw agent |

The Chat tab is a thin client: it POSTs to the AI exam's n8n webhook, so the same agent answers in the app, on Telegram and on Slack. No agent / RAG code lives in the RN app.

## Screenshots (bilag)

Screenshots from a live run against the Helmut stack (appendix A–G; the source-code / n8n walkthrough is H–M, used in the report).

<table>
<tr>
<td align="center"><b>A · Login</b><br><sub>Firebase email/password gate</sub><br><img src="bilag/bilag-A-ios-Login.jpg" width="200"></td>
<td align="center"><b>B · Harbour</b><br><sub>dual live cams + YOLOv11m boxes</sub><br><img src="bilag/bilag-B-ios-Harbour.jpg" width="200"></td>
<td align="center"><b>C · Fleet · in port</b><br><sub>skipaskrárnúmer + mbl.is link</sub><br><img src="bilag/bilag-C-ios-Fleet-inPort.jpg" width="200"></td>
<td align="center"><b>D · Fleet · at sea</b><br><sub>live speed (kn) from AIS</sub><br><img src="bilag/bilag-D-ios-Fleet-atSea.jpg" width="200"></td>
</tr>
<tr>
<td align="center"><b>E · mbl.is skipaskrá</b><br><sub>deep link from a Fleet card</sub><br><img src="bilag/bilag-E-ios-ext-link-from-Fleet.jpg" width="200"></td>
<td align="center"><b>F · Chat · status</b><br><sub>live status &amp; hull 2904</sub><br><img src="bilag/bilag-F-ios-Chat-status.jpg" width="200"></td>
<td align="center"><b>G · Chat · camera vision</b><br><sub>describes the cam-N frame</sub><br><img src="bilag/bilag-G-ios-Chat-description.jpg" width="200"></td>
</tr>
</table>

## Run

```bash
cd sundahofn-spotter
npm install
npx expo start        # open in Expo Go on an iPhone
```

## Layout

```
rn/
├── sundahofn-spotter/   the Expo app (App.js, screens/, lib/, components/)
├── bilag/               exam appendix — app screenshots (A–G, shown above) + source-code/n8n walkthrough images (H–M, used in the report)
├── README.md            this file
└── exam-requirments.md  the RN course brief
```

## Source-code & n8n walkthrough (bilag H–M)

The code and workflow appendix images at full size:

![H1 · App.js — skeleton](bilag/bilag-H1-appjs-skeleton.png)
![H2 · App.js — auth gate + tab view](bilag/bilag-H2-appjs-auth-n-view.png)
![I1 · LiveScreen — consts + functions](bilag/bilag-I1-LiveScreen-const-n-functions.png)
![I2 · LiveScreen — ScrollView](bilag/bilag-I2-LiveScreen-scrollview.png)
![J1 · VesselScreen — load + ScrollView](bilag/bilag-J1-VesselScreen-load-n-scrollview.png)
![J2 · VesselScreen — vessel row](bilag/bilag-J2-VesselScreen-vesselrow.png)
![K1 · ChatScreen — send](bilag/bilag-K1-ChatScreen-send.png)
![K2 · ChatScreen — FlatList + TextInput](bilag/bilag-K2-ChatScreen-flatlist-n-textinput.png)
![L · api.js — backend + webhook URLs](bilag/bilag-L-apijs-URL.png)
![M · n8n — chat workflow](bilag/bilag-M-n8n-workflow.png)
