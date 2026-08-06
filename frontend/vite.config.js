import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// En Docker Compose, le backend est un conteneur séparé joignable par son nom
// de service ('backend'), pas par 127.0.0.1 ; en local sans Docker, 127.0.0.1
// convient. Cf. docker-compose.yml (BACKEND_URL=http://backend:8000).
const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // En dev, le frontend tourne sur un port séparé (5173) ; en prod, il
      // est servi par FastAPI dans le même conteneur (cf. backend/app/main.py),
      // donc /api est same-origin et ce proxy ne sert qu'en local. Ce choix
      // (proxy plutôt qu'un VITE_API_URL + CORS côté FastAPI) évite d'avoir
      // à ouvrir CORS sur le backend juste pour le confort du dev local.
      '/api': backendUrl,
    },
  },
})
