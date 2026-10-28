# Landing page deployment

The static site lives in `site/`. That folder contains only the files the page loads: its HTML, CSS, favicon, and two local illustrations. The Python CLI and its configuration stay outside the deployed assets.

## Cloudflare Workers static assets

From the project root, Wrangler reads `wrangler.jsonc` and publishes only `./site`:

```bash
npx --yes wrangler@4.102.0 deploy
```

For a temporary public preview, use:

```bash
npx --yes wrangler@4.102.0 deploy --temporary --name token-usage-moderation --compatibility-date 2026-10-27 --assets ./site
```

The temporary preview is public to anyone with its URL and is short-lived. Keep any one-time claim link private; do not paste it into project files, issues, or logs.

## Cloudflare Pages

The separate `wrangler.pages.jsonc` config points Pages at the same static folder. After creating a Pages project, deploy from the project root with:

```bash
npx --yes wrangler@4.102.0 pages deploy ./site --project-name token-usage-moderation --config ./wrangler.pages.jsonc
```

For a GitHub-connected Cloudflare Pages project, choose no framework, leave the build command empty, and use `site` as the build output directory. The repo remains the source of truth, while only the static folder is published.

## GitHub Pages

An optional manual-only workflow is included at `.github/workflows/landing-page.yml`. In GitHub repository settings, select **Pages → Source → GitHub Actions**. Run **Publish landing page to GitHub Pages** when you choose to publish. The workflow uploads only `site/` as the Pages artifact; it does not run automatically on pushes.

The HTML uses relative asset paths and also works below a GitHub repository subpath. Do not publish the repository root as site output. For a GitHub-to-Cloudflare deployment path, use the Cloudflare Git integration above or run the Workers command from this repo; no GitHub push or account configuration is performed by these files alone.
