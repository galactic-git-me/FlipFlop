FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies using legacy-peer-deps to avoid the version clashes you experienced
RUN npm install --legacy-peer-deps

# Copy the rest of the application
COPY . .

# Disable telemetry
ENV NEXT_TELEMETRY_DISABLED=1

# Build the Next.js application
RUN npm run build

# Expose the port the app runs on
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
