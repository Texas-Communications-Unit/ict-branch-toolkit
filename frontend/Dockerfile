FROM node:24.14-alpine AS development
RUN corepack enable && corepack prepare pnpm@11.9.0 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile=false
COPY . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

FROM development AS build
RUN pnpm build

FROM nginx:1.29-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

