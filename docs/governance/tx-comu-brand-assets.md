# TX-COMU brand asset provenance

## Authority

The Texas Communications Unit organization repository is the identity source of
truth:

- Upstream repository: `Texas-Communications-Unit/.github`
- Upstream commit: `567acbe4166ad2d6e7b9c283cf04b658915c1b98`
- Brand guide: `brand/README.md`
- Logo inventory and usage rules: `brand/assets/logos/README.md`
- Digital color tokens: `brand/assets/colors/tx-comu-colors.css`

The vendored files are exact copies. They must not be redrawn, traced,
recolored, cropped, stretched, rotated, outlined, or given effects.

## Vendored inventory

| Local path                                           | Upstream path                                            | Purpose                                 | SHA-256                                                            |
| ---------------------------------------------------- | -------------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------ |
| `frontend/public/brand/tx-comu-logo-transparent.svg` | `brand/assets/logos/originals/TX-COMU (transparent).svg` | Preferred scalable application identity | `153a194fdfe0bdbd2a791f5d598048e95af2d66dbe6dc5a71790ac930f666fa1` |
| `frontend/public/brand/tx-comu-logo.png`             | `brand/assets/logos/tx-comu-logo.png`                    | PNG fallback artwork                    | `5fd6b8afa4654c75525a96cf850efdf49d967bcadd03b41814367ed989c9d778` |
| `frontend/public/brand/tx-comu-app-icon.png`         | `brand/assets/logos/tx-comu-github-avatar.png`           | Square favicon and application icon     | `8ac4166e05b58c689a53b41544138f8e5faba2b64fe5ca801eb11d847dcdc853` |

Only these three assets are vendored. Expanded incident-symbol and Tactical
Chicken variants remain at the authoritative source because routine application
identity does not require them.

## Digital implementation

The application defines the approved digital tokens once as CSS custom
properties:

- Navy `#10233F`
- Blue `#1F5F99`
- Slate `#465466`
- Light `#F4F7FB`
- White `#FFFFFF`
- Red `#D72638`

MapLibre reads the same custom properties for the offline background, site
markers, and manual rings. Ring type remains available as text and data, so
color is not the only carrier of meaning.

## Rights and approval

ICT Branch Toolkit software remains licensed under GNU AGPL v3. The Texas
Communications Unit and TX-COMU names, logos, and identifying marks remain
organizational brand assets. Their inclusion does not relicense the marks under
the software license or authorize a third party to imply sponsorship,
endorsement, affiliation, credentialing authority, or official State of Texas
status.

TX-COMU leadership or its designated maintainer must approve the final visual
treatment and confirm correct logo use before merge or deployment.
