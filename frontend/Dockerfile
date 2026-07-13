FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# Dev-Server-Modus für die Demo (kein separater Build/Nginx-Schritt nötig).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
