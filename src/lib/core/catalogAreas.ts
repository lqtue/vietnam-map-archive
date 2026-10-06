/** Curated coverage destinations. Names refer to the pre-July-2025 boundary set. */
export const CATALOG_AREAS = [
  {
    slug: 'ho-chi-minh',
    name: 'Hồ Chí Minh',
    en: {
      title: 'Historical maps of Saigon (Ho Chi Minh City)',
      label: 'Saigon / Ho Chi Minh City',
      intro:
        'Explore old maps of Saigon and the surrounding area, now part of Ho Chi Minh City. Compare dated sheets, read their original titles, and follow each record back to the institution holding the scan.',
    },
    vi: {
      title: 'Bản đồ Sài Gòn xưa — Thành phố Hồ Chí Minh',
      label: 'Sài Gòn / Thành phố Hồ Chí Minh',
      intro:
        'Khám phá bản đồ Sài Gòn xưa và vùng phụ cận, nay thuộc Thành phố Hồ Chí Minh. Đối chiếu các bản đồ theo năm, đọc nhan đề gốc và tìm nguồn lưu giữ từng bản đồ.',
    },
  },
  {
    slug: 'ha-noi',
    name: 'Hà Nội',
    en: {
      title: 'Historical maps of Hanoi (Hà Nội)',
      label: 'Hanoi / Hà Nội',
      intro:
        'Explore old maps of Hanoi and its surroundings. Browse sheets in chronological order to compare streets, waterways and the extent of the city, with dates and source institutions recorded for each map.',
    },
    vi: {
      title: 'Bản đồ Hà Nội xưa',
      label: 'Hà Nội',
      intro:
        'Khám phá bản đồ Hà Nội xưa và vùng phụ cận. Xem bản đồ theo trình tự thời gian để đối chiếu đường phố, sông ngòi và phạm vi đô thị, cùng thông tin niên đại và nơi lưu giữ từng bản đồ.',
    },
  },
  {
    slug: 'thua-thien-hue',
    name: 'Thừa Thiên Huế',
    en: {
      title: 'Historical maps of Huế and Thừa Thiên Huế',
      label: 'Huế / Thừa Thiên Huế',
      intro:
        'Explore old maps of Huế and the surrounding Thừa Thiên Huế area. Browse dated city plans and survey sheets, view their scans, and consult the original institutions for source information.',
    },
    vi: {
      title: 'Bản đồ Huế xưa và Thừa Thiên Huế',
      label: 'Huế / Thừa Thiên Huế',
      intro:
        'Khám phá bản đồ Huế xưa và vùng Thừa Thiên Huế. Xem bản đồ đô thị và các tờ bản đồ khảo sát theo niên đại, mở bản quét và tra cứu thông tin từ cơ quan lưu giữ bản gốc.',
    },
  },
] as const;

export function coverageAreas(row: { regions?: unknown; region?: unknown }): string[] {
  if (Array.isArray(row.regions) && row.regions.length)
    return row.regions.filter((v): v is string => typeof v === 'string');
  return typeof row.region === 'string' && row.region ? [row.region] : [];
}

export function matchesCoverageArea(
  row: { regions?: unknown; region?: unknown },
  selected: readonly string[]
): boolean {
  return !selected.length || coverageAreas(row).some((name) => selected.includes(name));
}

/** Compact navigation label; full coverage remains available to filters and tooltips. */
export function catalogAreaSummary(row: { regions?: unknown; region?: unknown }) {
  const areas = [...new Set(coverageAreas(row))];
  const cityPriority = [
    'Hồ Chí Minh',
    'Hà Nội',
    'Đà Nẵng',
    'Hải Phòng',
    'Cần Thơ',
    'Thừa Thiên Huế',
    'Huế',
  ];
  const preferred = cityPriority.find((city) => areas.includes(city));
  const primary =
    preferred ||
    (typeof row.region === 'string' && areas.includes(row.region) ? row.region : areas[0]);
  const ordered = primary ? [primary, ...areas.filter((area) => area !== primary)] : [];
  const label = primary === 'Hồ Chí Minh' ? 'HCMC' : primary === 'Thừa Thiên Huế' ? 'Huế' : primary;
  return {
    primary: primary || '—',
    label: label ? `${label}${areas.length > 1 ? ` +${areas.length - 1}` : ''}` : '—',
    full: ordered.join(', '),
  };
}
