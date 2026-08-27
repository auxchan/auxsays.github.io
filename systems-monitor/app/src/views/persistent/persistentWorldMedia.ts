import type { PersistentWorldPlacement, PersistentWorldReadModel } from "../../data/persistentWorldModel";

export interface PersistentWorldMedia {
  imageUrl: string;
  alt: string;
  sourcePage: string;
  license: "PUBLIC_DOMAIN" | "CC0_1_0";
  credit: string;
}

const media = {
  people: {
    imageUrl: "/systems-monitor/__local-review/media/employment-exposure-public-domain.jpg",
    alt: "Warehouse employees preparing packages for shipment at an industrial depot.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:Warehouse_workers_prepare_packages_for_shipment_at_Sharpe_Army_Depot_-_DPLA_-_414220df83b823977c05c01a4b6b4106.jpeg",
    license: "PUBLIC_DOMAIN",
    credit: "U.S. Department of Defense / National Archives"
  },
  industry: {
    imageUrl: "/systems-monitor/__local-review/media/industrial-demand-public-domain.jpg",
    alt: "Production workers completing an aircraft on an outdoor assembly line.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:On_North_American%27s_outdoor_assembly_line1a35297v.jpg",
    license: "PUBLIC_DOMAIN",
    credit: "Alfred T. Palmer / Library of Congress"
  },
  refining: {
    imageUrl: "/systems-monitor/__local-review/media/petroleum-refining-public-domain.jpg",
    alt: "Dusk view of a petroleum refinery with illuminated processing towers and pipework.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:Industrial-720706_640.jpg",
    license: "PUBLIC_DOMAIN",
    credit: "Carol M. Highsmith / Library of Congress"
  },
  storage: {
    imageUrl: "/systems-monitor/__local-review/media/product-storage-public-domain.jpg",
    alt: "Rows of petroleum storage tanks at an industrial tank farm.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:Petroleum_Storage_Tanks_-_DPLA_-_1802f5b6546765dfcfa9750b2e75fb37.jpg",
    license: "PUBLIC_DOMAIN",
    credit: "Hennepin County Library / DPLA"
  },
  utilities: {
    imageUrl: "/systems-monitor/__local-review/media/industrial-utilities-public-domain.jpg",
    alt: "Outdoor electrical substation with transformers, conductors, and switching equipment.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:Outdoor_power_substation.jpg",
    license: "PUBLIC_DOMAIN",
    credit: "Steve Karg"
  },
  energy: {
    imageUrl: "/systems-monitor/__local-review/media/refined-fuel-supply-public-domain.jpg",
    alt: "Trans-Alaska pipeline crossing open terrain toward the horizon.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:Trans-Alaska_Pipeline.jpg",
    license: "PUBLIC_DOMAIN",
    credit: "U.S. Department of the Interior"
  },
  trade: {
    imageUrl: "/systems-monitor/__local-review/media/distribution-port-public-domain.jpg",
    alt: "Aerial view of a container port with cranes, ships, roadways, and stacked freight.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:Aerial_photograph_of_the_Port_of_Miami_Container_Port.jpg",
    license: "PUBLIC_DOMAIN",
    credit: "James R. Tourtellotte / U.S. Customs and Border Protection"
  },
  freight: {
    imageUrl: "/systems-monitor/__local-review/media/freight-intermodal-cc0.jpg",
    alt: "Double-stack intermodal freight train moving containers through a rail network.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:Intermodal_train_01.jpg",
    license: "CC0_1_0",
    credit: "Wikideas1"
  },
  supply: {
    imageUrl: "/systems-monitor/__local-review/media/commercial-crude-supply-public-domain.jpg",
    alt: "Oil pumpjack operating against a clear sky in Electra, Texas.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:A_pumpjack,_sometimes_called_a_%22grasshopper%22_oil_pump_because_of_its_appearance,_on_the_outskirts_of_Electra,_a_small_city_in_Wichita_County,_Texas_LCCN2014633920.tif",
    license: "PUBLIC_DOMAIN",
    credit: "Carol M. Highsmith / Library of Congress"
  },
  government: {
    imageUrl: "/systems-monitor/__local-review/media/us-capitol-public-domain.jpg",
    alt: "Historic view of the United States Capitol framed by trees in Washington, D.C.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:CAPITOL,_U.S._LCCN2016867207.jpg",
    license: "PUBLIC_DOMAIN",
    credit: "Harris & Ewing / Library of Congress"
  },
  centralBank: {
    imageUrl: "/systems-monitor/__local-review/media/federal-reserve-eccles-public-domain.jpg",
    alt: "The Marriner S. Eccles Federal Reserve Board Building in Washington, D.C.",
    sourcePage: "https://commons.wikimedia.org/wiki/File:US_Federal_Reserve_Eccles_Building_1937.jpg",
    license: "PUBLIC_DOMAIN",
    credit: "Board of Governors of the Federal Reserve System"
  }
} as const satisfies Record<string, PersistentWorldMedia>;

function mediaKey(label: string, sector: number): keyof typeof media {
  const text = label.toLowerCase();
  if (/freight|transport|bottleneck|shipment|rail/.test(text)) return "freight";
  if (/fiscal|regulat|policy|geopolitical/.test(text)) return "government";
  if (/rate|credit|yield|financial|bank|mortgage|delinquen/.test(text)) return "centralBank";
  if (/trade|tariff|import|export|retail|consumer|spending|demand/.test(text)) return "trade";
  if (/energy|fuel|oil|gas|pipeline/.test(text)) return "energy";
  if (/storage|inventory|saving|stock/.test(text)) return "storage";
  if (/power|utility|electric|grid/.test(text)) return "utilities";
  if (/refin|manufactur|industrial|production|output|construction|capital|investment|automation|technology|business/.test(text)) return "industry";
  if (/labor|employment|worker|wage|earnings|hours|hire|job|layoff|participation|population|skills|education|retirement|caregiving|migration/.test(text)) return "people";
  return (["industry", "trade", "people", "people", "industry", "utilities", "people", "industry", "people", "trade"] as const)[Math.max(0, sector)] ?? "industry";
}

/** Uses reviewed local public-domain/CC0 media; fixture descendants inherit their named parent's context. */
export function persistentWorldMediaFor(model: PersistentWorldReadModel, placement: PersistentWorldPlacement): PersistentWorldMedia {
  const factor = model.factors[placement.canonicalFactorId];
  const parent = placement.parentPlacementId ? model.placements[placement.parentPlacementId] : undefined;
  const contextLabel = factor.evidencePosture === "TEST_FIXTURE" && parent ? model.factors[parent.canonicalFactorId].label : factor.label;
  return media[mediaKey(contextLabel, placement.sector)];
}
