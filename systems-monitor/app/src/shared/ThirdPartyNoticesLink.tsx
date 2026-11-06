// The bundle is minified without the licence comments of the open-source packages it contains; the
// build serves their notices beside it at this fixed URL (scripts/third-party-notices.mjs, NOTICES_URL).
// The built-site check refuses a bundle that does not contain this exact string.
export const THIRD_PARTY_NOTICES_URL = "/systems-monitor/THIRD_PARTY_NOTICES.txt";

export function ThirdPartyNoticesLink() {
  return <a className="sm-notices-link" href={THIRD_PARTY_NOTICES_URL}>Third-party software notices</a>;
}
