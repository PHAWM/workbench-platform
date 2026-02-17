FROM node:22.22.0-alpine AS build
WORKDIR /app
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
# Expose the port serve will run on
EXPOSE 3000
# Serve the built files
CMD ["npx", "serve","-s", "dist", "-l", "3000"]