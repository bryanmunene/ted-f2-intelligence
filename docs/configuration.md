# Configuration Guide

## Runtime Configuration

Environment variables are loaded with the `APP_` prefix. Key values:

- `APP_DATABASE_URL`
- `APP_SECRET_KEY`
- `APP_TED_API_BASE_URL`
- `APP_TED_SEARCH_PATH`
- `APP_TED_REQUESTS_PER_MINUTE`
- `APP_TED_CACHE_TTL_SECONDS`
- `APP_UI_TIMEZONE`

## Externalized Scoring Assets

- `config/keyword_pack.yaml` contains scoring weights, term groups, timing rules, strategic weighting, and qualification question templates.
- `config/search_profiles.yaml` defines analyst-friendly search strategies and lock sensitivity.

## Authentication Preparation

- `APP_AUTH_ENABLED=false` uses a configured internal actor context.
- `APP_AUTH_ENABLED=true` expects reverse-proxy identity headers.

