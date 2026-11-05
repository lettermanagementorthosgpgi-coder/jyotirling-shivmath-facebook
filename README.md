# Jyotirling Shivmath — Facebook Video Page Builder

This repository is intentionally standalone. The automation in this repository does not modify any other GitHub repository.

## What it does

1. Reads videos belonging to the configured Facebook Page through Meta Graph API.
2. Creates one static HTML page per video under `public/facebook/`.
3. Writes a Facebook sitemap at `public/sitemap-facebook.xml`.
4. Keeps a small JSON index to avoid generating duplicate pages.

The first version is **read-only**: it does not publish, edit, delete, or upload anything to Facebook.

## Required GitHub Actions secrets

Add these under **Settings → Secrets and variables → Actions → New repository secret**:

- `FB_PAGE_ID` — numeric ID of the Facebook Page.
- `FB_PAGE_ACCESS_TOKEN` — Page access token with permission to read Page-owned content.

Do not put tokens in source files, workflow YAML, or chat messages.

## Repository variables (optional)

- `SITE_BASE_URL` — canonical website base URL, for example `https://jyotirlingshivmath.in`.
- `FB_GRAPH_API_VERSION` — defaults to `v26.0`.

## Meta permissions

For reading content owned by a Page, Meta documents `pages_read_engagement` and `pages_show_list` as relevant Page permissions. The Page access token must belong to a person who can access the Page. Meta may require app review / advanced access depending on how the app is used.

References:
- [Meta Page API reference](https://developers.facebook.com/docs/graph-api/reference/page/)
- [Meta permissions reference](https://developers.facebook.com/docs/permissions/)

## Run

The initial GitHub Actions workflow is manual-only. After adding the secrets:

1. Open **Actions**.
2. Select **Build Facebook video pages**.
3. Click **Run workflow**.
4. Review the generated files in `public/facebook/` and `public/sitemap-facebook.xml`.

## Important deployment boundary

This repository can build and store the static pages. It does not change the existing website repository or configure the live website. The destination and deployment method for the live `/facebook/` URL must be confirmed separately before any external repository is touched.
