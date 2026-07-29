# ADR-0007: Bounded local-token lifecycle

- Status: Accepted for the non-production P1.6 prototype
- Date: 2026-07-27
- Decision owners: Project maintainers

## Context

The P1.1 prototype issued one Django REST Framework token per local account. The token had no
maximum lifetime, a new sign-in reused it, and the browser had no server-backed sign-out action.
That was not an acceptable lifecycle for the P1.6 release-candidate baseline.

Issue #23 separately proposes a standards-based TX-COMU single-sign-on design. This decision does
not implement or pre-approve that integration. The toolkit remains independently deployable and
continues to reject unimplemented identity providers.

## Decision

- Local tokens expire after `ICT_TOKEN_TTL_SECONDS`; the Issue #23 approved default is 43,200
  seconds (12 hours).
  The application refuses a zero or negative lifetime at startup.
- Each successful local sign-in revokes the account's previous token and issues a new random token.
  A user therefore has at most one valid local token.
- The token response includes an absolute `expires_at` value. The browser stores the token and
  expiration in session storage, removes both when the expiration is reached or an authenticated
  API request returns `401`, and requires the user to sign in again.
- `POST /api/auth/logout/` revokes the presented token before returning `204`.
- Django's active-account check remains authoritative on every authenticated request. Disabling an
  account therefore invalidates its token even before its configured expiration.
- Successful sign-in and sign-out create append-only audit events. Audit details contain the
  expiration timestamp only; token values, passwords, cookies, and request bodies are never
  recorded.
- Tokens are never accepted in query strings and are not persisted in local storage. TLS remains
  mandatory outside local development.

## Operational consequences

- Changing a password does not by itself revoke an already issued token. For suspected compromise,
  disable the account immediately and revoke its token through controlled administration before
  restoring access.
- Changing `ICT_TOKEN_TTL_SECONDS` affects the validity calculation for every existing token. A
  shorter setting can expire current sessions immediately.
- There is no refresh token. Reauthentication is deliberate at the end of the bounded session.
- The local-token flow still does not provide multifactor authentication, external federation,
  automated CiviCRM eligibility synchronization, or self-service password recovery. The system
  remains a non-production prototype until the relevant human security gate accepts those limits
  or a separately reviewed identity design replaces them.
