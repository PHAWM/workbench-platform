/**
 * Return the tenant ID for this deployment.
 *
 * VITE_TENANT_ID is set at build time per tenant (e.g. "uni_glasgow").
 * It is empty/absent for the superuser deployment.
 *
 * Because each tenant is a separate build deployed under its own base path
 * (/workbench/<tenantId>/), there is no need to parse the URL — the tenant
 * is simply a build-time constant.
 */
export const resolveTenantId = () =>
  import.meta.env.VITE_TENANT_ID || null;

/**
 * tenantPath is kept for compatibility but is a no-op here.
 *
 * React Router's basename already scopes all navigate() calls to
 * /workbench/<tenantId>/ automatically, so no path prefix is needed.
 */
export const tenantPath = (path) => path;

/**
 * Decode the `tid` claim from a JWT without verifying the signature.
 * Returns null if the token can't be parsed (malformed / not a JWT).
 * The backend still validates the signature on every request — this is
 * only used client-side to detect a tenant mismatch.
 */
export const getTenantFromToken = (token) => {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4);
    const json = atob(padded);
    return JSON.parse(json).tid ?? null;
  } catch {
    return null;
  }
};
