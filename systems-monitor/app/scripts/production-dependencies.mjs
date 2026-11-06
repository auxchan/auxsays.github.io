// The production dependency set of the Systems Monitor bundle, read from the committed lockfile.
//
// ONE predicate, shared by the licence inventory (DEPENDENCY_LICENSE_INVENTORY.json) and the
// third-party notices (THIRD_PARTY_NOTICES.txt), so the two can never describe different sets: every
// lockfile package that is not dev-only and has a version, keyed by name@version. A package installed
// at several paths with the same version is one entry; `paths` keeps every install path, sorted, so a
// reader of the installed files can pick one deterministically.
export function productionPackages(lock) {
  const packages = new Map();
  for (const [packagePath, metadata] of Object.entries(lock.packages ?? {})) {
    if (!packagePath || metadata.dev === true || !metadata.version) continue;
    const name = metadata.name ?? packagePath.split("node_modules/").at(-1);
    const key = `${name}@${metadata.version}`;
    const paths = [...(packages.get(key)?.paths ?? []), packagePath].sort();
    packages.set(key, {
      name,
      version: metadata.version,
      license: metadata.license ?? "UNKNOWN",
      resolved: metadata.resolved ?? null,
      paths
    });
  }
  return packages;
}
