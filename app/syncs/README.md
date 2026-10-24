# Syncs

The only place where concepts meet (`docs/concepts/syncs.md`). One function per sync, no business logic beyond the sync's `where` condition. This layer may import module public entries (`app.modules.<name>_v<N>`), `app/adapters`, `app/flags.py` and `app/settings.py`.
