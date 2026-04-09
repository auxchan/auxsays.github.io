# AUXSAYS site bundle

This bundle is ready for GitHub Pages on your existing `auxchan/auxsays.github.io` repository.

## What is included
- Home page
- Portfolio page
- Articles index with search, categories, and tags
- Static article generation from markdown files in `content/articles`
- Browser-based admin page at `/admin/`
- GitHub Pages Actions workflow
- Lottie-ready icon framework with fallbacks
- Download file support
- Mobile responsive layout

## Important note about the admin
The admin page uses the GitHub REST API directly from the browser.

To save articles from `/admin/`, create a fine-grained personal access token for this repository with:
- Repository access: only `auxchan/auxsays.github.io`
- Repository permissions: Contents = Read and write

Then paste the token into the admin page.

## Custom font
The site is already wired to use `AUX Triad Fusion` if the font file exists at:

`/assets/fonts/AUX-TriadFusion-v13-Regular.otf`

The font file is not included in this bundle.
If you want your custom font live on the site, create the folder `assets/fonts/` and place your font file there using that exact filename.

## Content editing without admin
You can also edit article files directly in:

`content/articles/`

Each article is a markdown file with front matter.

## Triggering a rebuild
Any commit to `main` triggers the GitHub Pages workflow and rebuilds the site.
