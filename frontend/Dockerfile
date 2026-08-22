FROM node:22-alpine AS base

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

FROM base AS development

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS build

ARG VITE_API_BASE_URL=/api
ARG VITE_APP_ENV=production
ARG VITE_APP_RELEASE=unknown

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_ENV=${VITE_APP_ENV} \
    VITE_APP_RELEASE=${VITE_APP_RELEASE}

RUN npm run build

FROM nginx:1.27-alpine AS production

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
