/** VMA's small, faceted adaptation of cartographic genre/form terminology.
 * https://guides.loc.gov/cataloging-cartographic-materials/genre-form-headings */
export const MAP_TYPES = [
  { key: 'general_reference', en: 'General reference', vi: 'Bản đồ địa lý tổng quát' },
  { key: 'city_plan', en: 'City / site plan', vi: 'Bản đồ đô thị / mặt bằng' },
  { key: 'topographic', en: 'Topographic', vi: 'Bản đồ địa hình' },
  { key: 'cadastral', en: 'Cadastral', vi: 'Bản đồ địa chính' },
  { key: 'hydrographic', en: 'Nautical / hydrographic chart', vi: 'Hải đồ / bản đồ thủy đạc' },
  { key: 'route', en: 'Route / transport map', vi: 'Bản đồ tuyến / giao thông' },
  { key: 'thematic', en: 'Thematic', vi: 'Bản đồ chuyên đề' },
] as const;

export const MAP_SUBJECTS = [
  { key: 'administrative_boundaries', en: 'Administrative boundaries', vi: 'Địa giới hành chính' },
  { key: 'urban_development', en: 'Urban development', vi: 'Phát triển đô thị' },
  { key: 'transport', en: 'Transport', vi: 'Giao thông' },
  { key: 'economic_activity', en: 'Economic activity', vi: 'Hoạt động kinh tế' },
  { key: 'military_operations', en: 'Military operations', vi: 'Hoạt động quân sự' },
  { key: 'land_ownership', en: 'Land ownership', vi: 'Quyền sở hữu đất' },
  { key: 'navigation', en: 'Navigation', vi: 'Hàng hải / đường thủy' },
  { key: 'geology', en: 'Geology', vi: 'Địa chất' },
  { key: 'population', en: 'Population', vi: 'Dân số' },
  { key: 'land_use', en: 'Land use', vi: 'Sử dụng đất' },
] as const;

export const DEPICTED_STATES = ['observed', 'proposed', 'mixed', 'unknown'] as const;
export const MAP_CONTENT_ROLES = ['main_map', 'index_map', 'legend', 'text', 'unknown'] as const;
export function canonicalMapType(value: string | null | undefined): string | null {
  if (value === 'plan') return 'city_plan';
  if (value === 'regional') return 'general_reference';
  return value || null;
}
export function mapTypeLabel(value: string | null | undefined, locale: 'en' | 'vi' = 'en'): string {
  const key = canonicalMapType(value);
  return (
    MAP_TYPES.find((type) => type.key === key)?.[locale] ??
    key ??
    (locale === 'vi' ? 'Chưa rõ' : 'Unknown')
  );
}
