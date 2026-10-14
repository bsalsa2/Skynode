# Name: Varn (formerly Skynode, then Talo)

**Status: decided and renamed in the repo. The trademark check is still open.**

## Decision

The project is called **Varn**. "Varn Labs" is an organization label only (the
footer, the copyright line, the site name). It is not a registered company, and
no copy should suggest that it is.

- Skynode was dropped because outside reviewers pointed out that it is already
  used by unrelated businesses.
- Talo was the interim name. It has been replaced everywhere in the code, tests,
  configs, docs, the dashboard and the website.

## Meaning

Varn is close to the Swedish word *värn* (protection, defense), and it sounds
like "warn". That fits a system that only watches and reports: it warns, it
never acts.

## Domain

`tryvarn.com` is registered and is the site's primary domain (canonical links and share images point at it).

## To do

- [ ] USPTO search for "Varn" in **Class 9** (software, cameras, detection
      hardware) and **Class 42** (SaaS, technology services). Not checked yet.
- [ ] Search the web and other trademark databases for "Varn" in the countries
      this project could reach (aerospace, drones, software).
- [x] Register `tryvarn.com`.
- [ ] Point `tryvarn.com` at Netlify (DNS) and set up the `@tryvarn.com` email address.
- [ ] Check the GitHub and social handles.
- [ ] Rename the Netlify project (`skynode-si`) and the Drive and Kaggle folders,
      which still use the old name, then update the links that point at them.
- [x] Decide on a name (Varn).
- [x] One pass over the repo, the website (`web/src/content.js`), the dashboard
      and the banner/social images.
- [x] Keep old installs working: `TALO_LAT` / `TALO_LON` are still read, and an
      old `logs/talo.db` is renamed to `logs/varn.db` the first time the brain
      starts.
