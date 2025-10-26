# Docker Setup for ZAPI Application

## Prerequisites
- Docker Desktop installed and running
- Docker Compose installed (usually comes with Docker Desktop)

## Quick Start

### 1. Configure Environment Variables
Copy the sample environment file and configure your credentials:
```bash
cp .env.sample .env
```

Edit `.env` and set your Z-API credentials:
- `ZAPI_INSTANCE_ID`: Your Z-API instance ID
- `ZAPI_INSTANCE_TOKEN`: Your Z-API instance token
- `SECRET_KEY`: A secure secret key for Flask sessions

### 2. Build and Run with Docker Compose

Build the Docker image:
```bash
docker-compose build
```

Start the application:
```bash
docker-compose up -d
```

The application will be available at: http://localhost:5055

### 3. View Logs
```bash
docker-compose logs -f zapi
```

### 4. Stop the Application
```bash
docker-compose down
```

## Docker Commands

### Rebuild after code changes:
```bash
docker-compose up --build -d
```

### Enter the container shell:
```bash
docker exec -it zapi /bin/bash
```

### View container status:
```bash
docker-compose ps
```

### Remove everything (including volumes):
```bash
docker-compose down -v
```

## Persistent Data

The following directories are mounted as volumes and persist between container restarts:
- `./instance`: SQLite database and instance data
- `./logs`: Application logs

## Troubleshooting

### Port 5055 already in use
If port 5055 is already in use, you can change it in `docker-compose.yml`:
```yaml
ports:
  - "YOUR_PORT:5055"
```

### Container fails to start
Check the logs:
```bash
docker-compose logs zapi
```

### Database issues
The database is stored in `./instance/database.db`. To reset:
1. Stop the container: `docker-compose down`
2. Delete the database: `rm instance/database.db`
3. Start the container: `docker-compose up -d`

## Development Mode

To run in development mode with auto-reload disabled (to prevent scheduler duplication):
1. Set `FLASK_ENV=development` in your `.env` file
2. Rebuild and restart: `docker-compose up --build -d`

Note: Auto-reload is disabled in the Docker container to prevent APScheduler from creating duplicate jobs.