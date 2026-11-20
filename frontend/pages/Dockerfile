# Build the pages app, then serve the static files with nginx.
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=http://localhost:8000
ARG VITE_VIEWER_URL=
ENV VITE_API_URL=$VITE_API_URL VITE_VIEWER_URL=$VITE_VIEWER_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s CMD wget -qO- http://localhost/ >/dev/null || exit 1
