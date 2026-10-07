# Security policy

## Reporting a vulnerability

Please don't open a public issue for a security problem. Use GitHub's private vulnerability reporting: go to the repository's **Security** tab and choose **Report a vulnerability**. That keeps the report between you and the maintainer until a fix is ready.

Include what you found, how to reproduce it, and what you think the impact is. You'll get a reply as soon as the maintainer can look at it. This is a one-person project run in spare time, so please allow some days, not hours.

## What's in scope

- The brain's dashboard server (`brain/dashboard.py`): anything that lets a web page or another device read files or the camera without access.
- The Pico firmware (`pico/`): anything that lets a network client move servos outside the configured limits.
- Secrets handling: a Wi-Fi password, a camera password, or a key ending up in git or in logs.

## What's not

- Denial of service from a device you already control on your own network.
- Findings in third-party packages. Report those upstream (Dependabot will also flag known ones here).

## Supported versions

Only the latest commit on `main` is supported. There are no releases with hardware yet.

## Secrets

Never commit real Wi-Fi details, camera passwords, or API keys. `pico/wifi_secrets.py` and `.env` files are gitignored. If you think a secret was committed, report it the same way and treat the secret as compromised.
