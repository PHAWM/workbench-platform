# PHAWM Frontend

A React-based web application for AI application auditing and performance analysis. This workbench provides tools for auditors to evaluate AI systems, define audit criteria, analyze performance metrics, and generate audit outcomes.

## Features

- **Dashboard** - Central hub for managing audits and navigating the application
- **AI Application Overview** - View and manage AI application details under audit
- **Audit Criteria** - Define and configure evaluation criteria with metrics and events
- **Performance Analysis** - Visualize and analyze AI system performance with charts and metrics
- **Audit Outcome** - Review and finalize audit results
- **User Authentication** - Secure login, registration, password reset, and invite-based onboarding

## Tech Stack

- **React 19** with React Router v6
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **D3.js & Recharts** for data visualizations
- **Radix UI** for accessible UI components
- **Lucide React** for icons

## Prerequisites

- Node.js (v18 or higher recommended)
- npm or yarn

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd workbench-frontend
   ```

2. Install dependencies:
   ```bash
   npm install --force
   ```

3. Create a `.env` file in the root directory:
   ```bash
   VITE_API_URL = "http://127.0.0.1:8000/api/v1"
   VITE_DOCS_URL = "http://127.0.0.1:8080"
   ```

## Development

Start the development server:

```bash
npm start
```

The app will be available at [http://localhost:3000](http://localhost:3000).

## Build

Create a production build:

```bash
npm run build
```

The optimized build will be output to the `dist` folder.

## Project Structure

```
src/
├── api/                    # API service layer
├── components/
│   ├── auth/               # Authentication components (login, register, password reset)
│   ├── event/              # Event management components
│   ├── metric/             # Metric forms and displays
│   ├── navigation/         # Navigation components
│   ├── onboarding/         # User onboarding flow
│   ├── popUp/              # Modal dialogs and popups
│   ├── ui/                 # Reusable UI components (buttons, cards, sliders)
│   └── visualizations/     # D3 and Recharts visualization components
├── context/                # React context providers
├── handlers/               # Business logic handlers
├── hooks/                  # Custom React hooks
├── pages/                  # Page components
├── utils/                  # Utility functions
├── App.jsx                 # Main application component
└── index.jsx               # Application entry point
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API base URL | `http://127.0.0.1:8000/api/v1` |
| `VITE_DOCS_URL` | Documentation server URL | `http://127.0.0.1:8080` |

## License

Private - All rights reserved.
