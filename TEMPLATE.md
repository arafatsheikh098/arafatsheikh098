# Make this profile yours

This profile page is generated. Every card is a hand-drawn SVG built from **one config file** plus live data from GitHub (and Codeforces, if you use it). It refreshes itself every day.

## 3 steps

1. **Create your copy.** Click **Use this template → Create a new repository** and name it **exactly your GitHub username** (e.g. `octocat/octocat`), set to Public. GitHub shows that repo's README on your profile.
2. **Edit `profile.yml`.** Change `handle`, `name`, taglines, featured repos and links. Anything you leave empty (`""` or `[]`) is hidden.
3. **Run the Action.** Go to **Actions → Build profile → Run workflow**, then **Snake → Run workflow**. A minute later your profile is live, and from then on it rebuilds daily.

> If the Actions tab asks you to enable workflows, enable them. If the build can't push, open **Settings → Actions → General → Workflow permissions** and choose **Read and write**.

## What you can change in `profile.yml`

| Key | What it does |
|---|---|
| `handle` | Your GitHub username (falls back to the repo owner) |
| `name`, `headline`, `location` | Banner text and chips |
| `taglines` | Lines that rotate under your name |
| `about`, `now_building` | The "About me" section |
| `start_here` | The "New here?" guide pointing visitors to a repo |
| `featured` | Repos drawn as big cards: optional `title`, `stack` chips, `tag` |
| `categories` | Groups for the collapsible "All projects" list; unlisted repos go to "More" |
| `descriptions` | Fill in for repos that have no GitHub description |
| `skills` | Icon ids from [skillicons.dev](https://skillicons.dev) |
| `codeforces` | Your handle, or `""` to hide the card |
| `links` | `linkedin`, `email`, `website`: shown as buttons when set |
| `theme` | `accent` / `accent2` colours for dark and light mode |
| `template_source` | Credit line in the footer, so people can find the template |

## Preview locally

```bash
pip install pyyaml markdown
python scripts/preview.py          # builds, then serves http://localhost:8000
```

The preview has a dark/light toggle. Data is cached for 6 hours in `.cache/`. Use `python scripts/build.py --refresh` to refetch.

## How it works

```
profile.yml ──┐
GitHub API ───┼──▶ scripts/build.py ──▶ assets/*.svg (dark + light) ──▶ README.md
Codeforces ───┘        (svg.py draws, sources.py fetches)
```

- Cards are plain SVG with CSS animation: no JavaScript, no external fonts, nothing for GitHub's image proxy to block. Viewers who prefer reduced motion get a still version.
- `<picture>` swaps the dark and light versions to match the viewer's GitHub theme.
- If an API is down, the last good card stays in place, so the page never breaks.
