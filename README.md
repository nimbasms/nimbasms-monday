# Nimba SMS monday.com App

This project provides a monday.com app that lets users send SMS through the
Nimba SMS API, both manually (one-click) and via automations. The solution is
split into a lightweight frontend (monday view) and a FastAPI backend that
talks to Nimba and monday GraphQL.

## What is hosted where

- **Frontend (client)**: Static HTML/JS/CSS in `frontend/`. It can be hosted on
  any static hosting provider. If your monday plan supports hosting, you can
  also host the frontend directly in monday.
- **Backend (server)**: FastAPI in `backend/`. It can run on your own server
  or any cloud provider. Some monday plans also allow hosting server-side
  components; if available, you can deploy the backend there.

## Features

- Manual SMS sending from a monday view.
- Automations endpoint for “when status changes, send SMS”.
- Sender list loaded from Nimba (`/v1/sendernames`).
- Optional updates to monday items (status/update body).

## Project structure

```
.
├── backend/   # FastAPI API (Nimba + monday GraphQL)
└── frontend/  # monday view (HTML/JS/CSS)
```

## Backend quickstart

1. Configure environment variables (see `backend/env.example`).
2. Install dependencies:
   ```
   pip install -r backend/requirements.txt
   ```
3. Run:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port 8080
   ```

Endpoints:

- `POST /monday/automation` – automation trigger
- `POST /monday/action` – manual action trigger
- `POST /sendernames` – fetch sender names
- `POST /nimba/dlr` – delivery reports

## Frontend quickstart

Serve the `frontend/` folder as a static site and point your monday view URL to
`index.html`.

App settings used by the frontend:

- `backendUrl`
- `phoneColumnId`
- `messageColumnId`
- `senderId`
- `statusColumnId`
- `statusLabel`
- `nimbaSid`
- `nimbaSecret`

## monday.com setup (high level)

1. Create a new app in the monday Developer Center.
2. Add a **Board View** (or Item View) pointing to your hosted frontend.
3. Add an **Integration** pointing to your backend automation URL.
4. Install the app in Draft mode and test.

## Notes

- Nimba SMS uses Basic Auth (`sid` + `secret`).
- Nimba endpoints default to `/v1/messages` and `/v1/sendernames`.
