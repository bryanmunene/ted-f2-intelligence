# Known Limitations

- The TED expert-query builder is centralized but conservative; field-level syntax may need tuning against current TED Search API behavior in the target environment.
- The app currently supports manual scans only. Scheduled scans and notifications are planned for later phases.
- v1 uses reverse-proxy header auth preparation rather than full SSO.
- Saved search UI is deferred even though the database table exists.

