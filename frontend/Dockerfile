FROM node:24.14-alpine AS development
RUN corepack enable && corepack prepare pnpm@11.9.0 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

FROM development AS build
ARG VITE_API_BASE_URL=""
ARG VITE_MAP_STYLE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_MAP_STYLE_URL=${VITE_MAP_STYLE_URL}
RUN pnpm build

FROM nginx:1.29-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
