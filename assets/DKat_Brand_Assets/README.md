# DKat — Official Logo Asset Pack (reconstructed)

**Brand:** DKat  
**Slogan:** Digital Key To All  
**Symbol:** D + K geometric monogram, from the latest user-approved visual direction (NOT the previous KD/KDat name).

## Files

- `SVG/dkat-logo-light.svg`, `SVG/dkat-logo-dark.svg`: horizontal icon + DKat wordmark without slogan.
- `SVG/dkat-logo-light-tagline.svg`, `SVG/dkat-logo-dark-tagline.svg`: horizontal logo + slogan DIGITAL KEY TO ALL.
- `SVG/dkat-icon-light.svg`, `SVG/dkat-icon-dark.svg`: standalone D+K monogram, transparent background.
- `SVG/dkat-icon-square-*.svg`: standalone transparent 512-square layout.
- `SVG/dkat-app-icon-*.svg`: app icon with white / dark card background.
- `PNG/`: raster PNG equivalents, fully transparent for all except `app-icon` and `favicon` files.
- `PNG/dkat-favicon-*-16/32/48/64/192/256.png`: favicons / app icons with a solid background.
- `Preview/dkat-brand-preview.png`: preview made from the exported SVG/PNG assets.
- `Preview/dkat-design-reference.png`: source brand-board image for visual comparison only.
- `colors.json`: theme palettes.

## Brand colors

Light: primary `#3156CF`, orange `#FB923C`, dark text `#172138`, background `#F5F7FD`.  
Dark: primary `#26C7A7`, mint `#8BE5D0`, background `#0B1422`.

## Usage in Next.js

Copy `SVG/*.svg` to `public/assets/dkat/`, then:

```jsx
<img src="/assets/dkat/dkat-logo-light-tagline.svg" alt="DKat — Digital Key To All" width={260} />
```

Switch to `dkat-logo-dark-tagline.svg` when the app is in dark mode.

## Note on fidelity

These are clean SVG vector outlines recreated from a rendered concept image, not the original editable Figma/Illustrator source. The monogram silhouette is traced from the approved D+K reference, and the wordmark/tagline are converted to font-independent SVG paths. Minor differences versus the reference image are possible.
