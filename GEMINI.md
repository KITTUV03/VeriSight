# VeriSight Project Guidelines & Rules

## Git Workflow
- **Continuous Push Policy**: Whenever changes are made (bug fixes, feature additions, test updates, documentation, or configuration updates), stage the changes (excluding sensitive files such as `.env`), commit them with a descriptive message, and push them to GitHub on the active tracking branch.
- **Secrets & Sensitive Data**: Never commit `.env` or unmasked API credentials. Always verify that `.gitignore` prevents secret leakage.
