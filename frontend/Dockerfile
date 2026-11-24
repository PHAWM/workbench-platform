FROM node:22.22.0-alpine AS build
WORKDIR /app

ARG VITE_TENANT_ID
ENV VITE_TENANT_ID=$VITE_TENANT_ID
ARG VITE_IS_DEMO=false
ENV VITE_IS_DEMO=$VITE_IS_DEMO

COPY package*.json ./
RUN npm install --force

COPY . .
RUN npm run build
# --- Production stage ---
FROM node:22.22.0-alpine AS prod
WORKDIR /app

# Install a tiny static file server
RUN npm install -g serve

# Copy built files from the build stage
COPY --from=build /app/dist ./dist
RUN echo '{"rewrites":[{"source":"**","destination":"/index.html"}],"headers":[{"source":"assets/**","headers":[{"key":"Cache-Control","value":"public, max-age=31536000, immutable"}]},{"source":"**/*.html","headers":[{"key":"Cache-Control","value":"no-store, must-revalidate"}]},{"source":"/","headers":[{"key":"Cache-Control","value":"no-store, must-revalidate"}]}]}' > ./dist/serve.json

# Expose the port serve will run on
EXPOSE 3000

# Serve the built files
CMD ["npx", "serve","-s", "dist", "-l", "3000"]