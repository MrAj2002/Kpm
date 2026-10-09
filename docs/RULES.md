# Website extraction rules

Paste a JSON object into the workflow's **rules** field. It is configuration data, never executed JavaScript. Blank preserves existing rules; `{}` restores generic extraction.

Generic mode recognizes public HTTPS `.mp4`, `.m3u8`, `.mkv`, `.m4v`, `.webm`, `.mov` and `.ogv` URLs. URLs in HTML5 video attributes and explicitly configured media elements may be extensionless. Relative paths, protocol-relative links, the HTML `<base>` element, HTML attribute entities and common slash escapes are resolved. Query strings are preserved.

## Match a custom player

For a page whose video element is `<div class="player" data-video="/media/movie.m3u8">`, use:

```json
{"videoSelector":".player[data-video]","videoAttribute":"data-video"}
```

The selector must identify a real media URL, not a web page that contains another player. This does not decode script functions or decrypt streams.

## Allow an external iframe player

```json
{"iframeHosts":["player.example.com"],"maxIframeDepth":2}
```

`player.example.com` illustrates the exact hostname field; replace it with the player host used by your actual website. Same-host iframes are allowed by default. An external host must be added explicitly. Wildcards and embedded URLs are not accepted. Set depth to zero to disable iframe scanning.

## Catalogue and episodes

The following is a complete rule object for a website whose actual markup has `.card` catalogue entries and `a.episode` episode links. It is a structural example, not a claim that an unspecified website has these selectors.

```json
{
  "catalogPath": "/browse?page={page}",
  "searchPath": "/search?q={query}&page={page}",
  "itemSelector": ".card",
  "linkSelector": "a[href]",
  "titleSelector": ".title",
  "posterSelector": "img",
  "posterAttribute": "data-src",
  "nextSelector": "a.next",
  "detailTitleSelector": "h1",
  "descriptionSelector": ".description",
  "episodeSelector": "a.episode[href]",
  "episodesReversed": false
}
```

Leave `linkSelector` or `episodeLinkSelector` blank/absent when the selected item is already the link. Other selectors are evaluated inside each item. List paths resolve relative to the submitted source URL; paths beginning with `/` start at the domain root. `{page}` begins at 1 and `{query}` is URL encoded. Further pages require a `{page}` placeholder, nonempty results and a matching `nextSelector`.

Episode numbers are assigned by list position. The engine expects oldest-first website order unless `episodesReversed` is true; it returns the newest-first ordering used by Aniyomi. It does not infer season or episode numbers from arbitrary text.

## Supported fields

| Field | Default / behavior |
| --- | --- |
| `catalogPath` | Absent: single-entry direct-page mode |
| `searchPath` | Absent: filters the current catalogue page; full pasted HTTPS URLs always open directly |
| `latestPath` | Absent: latest feed disabled |
| `itemSelector` | Required for catalogue/search/latest paths |
| `linkSelector`, `titleSelector` | Blank: use the item itself |
| `posterSelector` | `img` |
| `posterAttribute` | `src` |
| `nextSelector` | Blank: no pagination |
| `detailTitleSelector` | `h1`, falling back to document title when not found; do not set an empty selector |
| `descriptionSelector` | Absent: explanatory source description |
| `episodeSelector` | Absent: one Play video episode |
| `episodeLinkSelector`, `episodeTitleSelector` | Blank: use the episode item |
| `episodesReversed` | `false`; set true for website newest-first lists |
| `videoSelector`, `videoAttribute` | Optional custom media selector; attribute defaults to `src` |
| `iframeSelector` | `iframe[src],iframe[data-src]`; use depth zero to disable frames |
| `iframeHosts` | Extra exact hostnames; at most 12 |
| `maxIframeDepth` | `2`; allowed range 0–3 |
| `sendReferer` | `true`; passes the page URL with extracted media |
| `scanScriptUrls` | `true`; reads plain quoted media URLs without executing scripts |
| `extraHeaders` | Optional `Accept`, `Accept-Language`, `User-Agent` and `Origin` values only |

Example public header configuration:

```json
{"extraHeaders":{"Accept-Language":"en-US,en;q=0.8"},"sendReferer":true}
```

Do not store passwords, cookies, authorization headers or private signed URLs. Source configurations are published. The engine does not preserve cookie sessions or bypass access controls.

## Bounds

The scanner limits each page to 4 MiB, a request to 30 seconds, redirects to six requests, recursive scans to eight pages, iframe links to five per page, catalogue results to 200 per page and media results to 100 per scanned page. URLs must use public HTTPS hosts on the default HTTPS port. Local/private destinations are rejected in URL checks and the page-fetching DNS resolver. Media playback is subsequently performed by Aniyomi's own networking stack.
