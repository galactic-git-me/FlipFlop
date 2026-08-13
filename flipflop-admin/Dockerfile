FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=development
ENV BACKEND_URL=http://backend:4311
ENV NEXT_PUBLIC_API_URL=http://localhost:4311

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["npm", "run", "dev"]
