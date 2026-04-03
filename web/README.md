# Axis Camera Config Web UI

Next.js frontend for the Axis Camera Config project.

## Purpose

The UI is the operator-facing layer for:

- entering camera targets manually
- uploading CSV or Excel camera lists
- reviewing camera summaries, time data, options, and capabilities
- applying supported write actions through the FastAPI backend
- managing stream profiles and firmware actions

## Run Locally

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Open `http://localhost:3000`.

## Backend Dependency

The frontend expects the FastAPI backend from the project root to be available at `http://localhost:8000` by default.

To point at a different backend, create `web/.env.local` with:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Main Areas

- `app/`: app router entrypoints and global styles
- `components/camera/`: camera workflow UI
- `components/ui/`: shared UI primitives
- `lib/`: API client, type definitions, and camera utility logic
- `public/`: static assets, including the camera CSV template used by the UI
