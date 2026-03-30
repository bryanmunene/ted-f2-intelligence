# Deployment Notes

## Intended Hosting Model

- Linux container
- PostgreSQL backing database
- reverse proxy terminating TLS in front of FastAPI
- enterprise networking and logging controls on cBrain infrastructure

## Checklist

- set a production secret key
- enable secure session cookies
- place the app behind HTTPS
- run `alembic upgrade head` as part of deployment
- restrict database credentials to the service account
- monitor rate-limit events and request counts

## Health Endpoints

- `/health/live`
- `/health/ready`

