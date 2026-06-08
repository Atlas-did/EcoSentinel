# EcoSentinel Dashboard (React + TypeScript + Vite)

React frontend for the EcoSentinel environmental monitoring system.

## Quick Start

```bash
npm install
npm run dev
```

The dev server starts at `http://localhost:3000` and proxies `/api` requests to the Python backend (default: `http://127.0.0.1:8080`).

If the backend is unavailable, the frontend degrades gracefully to simulated data.

## Build

```bash
npm run build
```

Output goes to `dist/`.

## Stack

- **React 19** + **TypeScript**
- **Vite** for dev/build
- **Tailwind CSS** v3 with shadcn/ui components
- **Recharts** for sensor/energy charts
- **Zustand** for state management
- **Axios** for API calls
