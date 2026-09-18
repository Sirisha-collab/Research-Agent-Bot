# React frontend setup

The Gradio UI is replaced by a React 19 + Vite 7 + TypeScript + Tailwind v4 app in `web/`.
The Python backend is unchanged except for two new report-download endpoints.

## Files in this update

| File | What it is |
| --- | --- |
| `backend/main.py` | replace — adds `/documents/{id}/report`, serves the built React app if present |
| `backend/core/report.py` | new — builds the Markdown report the UI downloads |
| `web/package.json` | new |
| `web/vite.config.ts` | new — dev proxy `/api` → `127.0.0.1:8000` |
| `web/tsconfig.json`, `web/tsconfig.app.json`, `web/tsconfig.node.json` | new |
| `web/index.html` | new |
| `web/.env.example` | new |
| `web/src/main.tsx` | new |
| `web/src/index.css` | new — Tailwind v4 theme tokens |
| `web/src/env.d.ts` | new |
| `web/src/types.ts` | new |
| `web/src/api.ts` | new — typed API client |
| `web/src/App.tsx` | new — layout and state |
| `web/src/components/*.tsx` | new — 9 components |

Unzip `research-assistant-web.zip` at the project root. It creates `web/` and overwrites
`backend/main.py`. `frontend/` (Gradio) and `run.py` can be deleted, or kept as a fallback.

Resulting layout:

```
research-assistant/
├── backend/
├── data/
├── web/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       ├── types.ts
│       ├── index.css
│       └── components/
├── requirements.txt
└── .env
```

## Development (two terminals)

**Terminal 1 — API**

```bash
cd research-assistant
.venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — web**

```bash
cd research-assistant/web
npm install
npm run dev
```

```bash
uvicorn backend.main:app --port 8000
```
