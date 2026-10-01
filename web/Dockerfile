FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID
ENV NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID
ARG NEXT_PUBLIC_LEGAL_OPERATOR_NAME
ENV NEXT_PUBLIC_LEGAL_OPERATOR_NAME=$NEXT_PUBLIC_LEGAL_OPERATOR_NAME
ARG NEXT_PUBLIC_LEGAL_CONTACT_EMAIL
ENV NEXT_PUBLIC_LEGAL_CONTACT_EMAIL=$NEXT_PUBLIC_LEGAL_CONTACT_EMAIL
ARG LEGAL_CONTENT_APPROVED
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public           ./public

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
