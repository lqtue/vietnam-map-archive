<!--
  GroupRow.svelte — the heading row of a grouped table: the group's name and its
  size, spanning every column. The row of `<tr>`s under it are the caller's.

  `count` is the group's full size, not the rows drawn under it, so a table that
  draws a slice still tells the truth. `/catalog` wrote this by hand; the text
  review table is the second table to group, which is when it earns a file.
-->
<script lang="ts">
  export let label: string;
  export let count: number;
  export let span: number;
</script>

<tr class="group-row">
  <td colspan={span}>
    <strong>{label}</strong>
    <span class="group-count">{count}</span>
  </td>
</tr>

<style>
  .group-row {
    background: var(--sb-group-bg);
  }
  .group-row td {
    padding: var(--space-2) var(--space-3);
    border-top: 1.5px solid var(--color-border);
    border-bottom: 1.5px solid var(--color-border);
  }
  .group-count {
    margin-left: var(--space-2);
    padding: 0.05rem 0.45rem;
    background: var(--color-text);
    color: var(--color-white);
    border-radius: var(--radius-pill);
    font-size: 0.72rem;
    font-weight: var(--font-extrabold);
  }
</style>
