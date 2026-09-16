# Multi-stage production image using Next.js `output: "standalone"`.
# https://github.com/vercel/next.js/tree/canary/examples/with-docker
# https://nextjs.org/docs/app/api-reference/config/next-config-js/output

FROM node:22-bookworm-slim AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

FROM base AS deps
COPY package.json package-lock.json ./
# Skip husky prepare (needs git hooks outside the image).
RUN npm ci --ignore-scripts

FROM base AS build
ARG API_ORIGIN=http://backend:8000
ARG NEXT_PUBLIC_API_ORIGIN=
ARG NEXT_PUBLIC_WIDGET_ORIGIN=
ARG NEXT_PUBLIC_STAFF_APP_ORIGIN=
ARG NEXT_PUBLIC_MARKETING_HOST_ORIGIN=
ARG NEXT_PUBLIC_DEMO_SITE_KEY=demo
ARG NEXT_PUBLIC_DEMO_PUBLIC_KEY=

ENV API_ORIGIN=$API_ORIGIN \
    NEXT_PUBLIC_API_ORIGIN=$NEXT_PUBLIC_API_ORIGIN \
    NEXT_PUBLIC_WIDGET_ORIGIN=$NEXT_PUBLIC_WIDGET_ORIGIN \
    NEXT_PUBLIC_STAFF_APP_ORIGIN=$NEXT_PUBLIC_STAFF_APP_ORIGIN \
    NEXT_PUBLIC_MARKETING_HOST_ORIGIN=$NEXT_PUBLIC_MARKETING_HOST_ORIGIN \
    NEXT_PUBLIC_DEMO_SITE_KEY=$NEXT_PUBLIC_DEMO_SITE_KEY \
    NEXT_PUBLIC_DEMO_PUBLIC_KEY=$NEXT_PUBLIC_DEMO_PUBLIC_KEY \
    NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS production
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY --from=build --chown=appuser:appuser /app/public ./public
RUN mkdir .next && chown appuser:appuser .next

COPY --from=build --chown=appuser:appuser /app/.next/standalone ./
COPY --from=build --chown=appuser:appuser /app/.next/static ./.next/static

USER appuser
EXPOSE 3000
CMD ["node", "server.js"]
