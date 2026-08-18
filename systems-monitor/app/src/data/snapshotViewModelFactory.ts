import type {
  NavigationNode,
  PublicationCandidate,
  PublicNavigationNode,
  PublicSnapshot,
  SnapshotViewModel
} from "./publicSnapshotTypes";

function resolveNodes(roots: PublicNavigationNode[], registry: Record<string, PublicNavigationNode>): NavigationNode[] {
  function resolve(node: PublicNavigationNode): NavigationNode {
    const { childRefs, ...viewNode } = node;
    const children = childRefs.map((reference) => resolve(registry[reference]));
    return children.length > 0 ? { ...viewNode, children } : viewNode;
  }
  return roots.map(resolve);
}

export function createSnapshotViewModel(snapshot: PublicSnapshot): SnapshotViewModel {
  return {
    ...snapshot,
    systems: resolveNodes(snapshot.systems, snapshot.extensions["auxsays.phase2.navigationNodes"])
  };
}

export function createCandidateViewModel(candidate: PublicationCandidate): SnapshotViewModel {
  const metadata = candidate.candidate;
  return {
    schemaVersion: metadata.targetSchemaVersion,
    contractVersion: metadata.targetContractVersion,
    snapshot: {
      id: metadata.id,
      evaluatedAt: metadata.evaluatedAt,
      generatedAt: metadata.generatedAt,
      asOf: metadata.asOf,
      sourceSnapshotId: metadata.sourceSnapshotId,
      publicationClass: metadata.publicationClass
    },
    ...candidate.payload,
    systems: resolveNodes(candidate.payload.systems, candidate.payload.extensions["auxsays.phase2.navigationNodes"])
  };
}
