<script lang="ts">
  import PageHero from '$lib/ui/PageHero.svelte';
  import { locale } from '$lib/core/i18n';
  import { atWidth, stepDown } from '$lib/core/iiif/thumbUrl';
  import type { PageData } from './$types';

  export let data: PageData;
  $: copy = data.area[$locale];
  $: vietnamese = $locale === 'vi';
  $: years = data.maps.flatMap((map) => (map.year == null ? [] : [map.year]));
  $: span = years.length ? [...new Set([Math.min(...years), Math.max(...years)])].join('–') : '';
  $: description = vietnamese
    ? `${data.maps.length} bản đồ lịch sử về ${copy.label}${span ? `, ${span}` : ''}. Xem bản quét, niên đại và nguồn lưu giữ tại Vietnam Map Archive.`
    : `${data.maps.length} historical maps covering ${copy.label}${span ? `, ${span}` : ''}. View scans, dates and source institutions in Vietnam Map Archive.`;
</script>

<svelte:head>
  <title>{copy.title} — Vietnam Map Archive</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={copy.title} />
  <meta property="og:description" content={description} />
</svelte:head>

<div class="page">
  <PageHero sub={description}>
    <svelte:fragment slot="title">{copy.title}</svelte:fragment>
  </PageHero>
  <main class="editorial-main">
    <p>{copy.intro}</p>
    <p>
      {vietnamese
        ? `Danh sách gồm các bản đồ có phạm vi địa lý giao với ${data.area.name}, theo ranh giới tỉnh trước tháng 7 năm 2025. Một số tờ cũng bao phủ các tỉnh lân cận; cách phân nhóm này không có nghĩa tên gọi hoặc ranh giới đó xuất hiện trên bản đồ gốc.`
        : `This collection includes maps whose geographic bounds overlap ${data.area.name}, using province boundaries before July 2025. Some sheets also cover neighbouring provinces; this grouping does not imply that these names or boundaries appeared on the original map.`}
    </p>
    <a href={`${vietnamese ? '/vi' : ''}/catalog?area=${encodeURIComponent(data.area.name)}`}
      >{vietnamese ? 'Tìm kiếm và lọc bản đồ' : 'Search and filter these maps'}</a
    >
    <h2>{vietnamese ? 'Bản đồ theo trình tự thời gian' : 'Maps in chronological order'}</h2>
    <ul id="area-maps">
      {#each data.maps as map (map.id)}
        <li>
          {#if map.thumbnail}
            <a
              class="preview"
              href={`/catalog/${map.slug}`}
              aria-label={map.name || (vietnamese ? 'Mở bản đồ' : 'Open map')}
            >
              <img
                src={atWidth(map.thumbnail, 200)}
                alt={map.name || ''}
                loading="lazy"
                width="120"
                height="90"
                on:error={(event) => stepDown(event, map.thumbnail ?? undefined)}
              />
            </a>
          {/if}
          <div class="map-record">
            <a href={`/catalog/${map.slug}`}>
              <strong>{map.name || (vietnamese ? 'Chưa có nhan đề' : 'Untitled')}</strong>
            </a>
            <span
              >{map.date_label ?? map.year ?? (vietnamese ? 'Chưa rõ niên đại' : 'Undated')}</span
            >
            {#if map.collection}<span>{map.collection}</span>{/if}
            {#if map.holding_institution}<span>{map.holding_institution}</span>{/if}
          </div>
        </li>
      {/each}
    </ul>
    <a href={vietnamese ? '/vi/catalog' : '/catalog'}
      >{vietnamese ? 'Khám phá kho bản đồ' : 'Browse the archive'}</a
    >
  </main>
</div>

<style>
  ul {
    list-style: none;
    padding: 0;
  }
  li {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    padding: var(--space-3) 0;
    border-bottom: var(--border-thin);
  }
  .map-record {
    flex: 1 1 16rem;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .preview img {
    display: block;
    object-fit: contain;
    background: var(--sb-thumb-bg);
    border: var(--border-thin);
  }
</style>
