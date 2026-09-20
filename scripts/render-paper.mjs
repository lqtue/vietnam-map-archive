import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const source = 'docs/paper/draft.md';
const output = 'docs/paper/blind-by-construction.tex';
const figuresDir = 'docs/paper/figures';

const esc = (value) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const svgText = (x, y, text, css = 'label') => text.split('\\n').map((line, i) => `<text x="${x}" y="${y + i * 23}" class="${css}">${esc(line)}</text>`).join('');
const box = (x, y, width, height, text, tone = 'blue') => `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="12" class="box ${tone}"/>${svgText(x + width / 2, y + height / 2 - (text.split('\\n').length - 1) * 11 + 7, text)}`;
const arrow = (x1, y1, x2, y2, dashed = false) => `<path d="M ${x1} ${y1} L ${x2} ${y2}" class="arrow${dashed ? ' dashed' : ''}" marker-end="url(#arrow)"/>`;
const svg = (width, height, content) => `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">\n<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#334155"/></marker><style>.box{stroke-width:2}.blue{fill:#e0f2fe;stroke:#0369a1}.amber{fill:#fef3c7;stroke:#b45309}.green{fill:#dcfce7;stroke:#15803d}.rose{fill:#ffe4e6;stroke:#be123c}.label{font:600 18px Arial,sans-serif;fill:#0f172a;text-anchor:middle;dominant-baseline:middle}.small{font:16px Arial,sans-serif;fill:#475569;text-anchor:middle}.arrow{stroke:#334155;stroke-width:2.5;fill:none}.dashed{stroke-dasharray:7 6}</style></defs>\n${content}\n</svg>`;

function writeFigure(name, content) {
	mkdirSync(figuresDir, { recursive: true });
	const svgPath = `${figuresDir}/${name}.svg`;
	const pdfPath = `${figuresDir}/${name}.pdf`;
	writeFileSync(svgPath, content);
	execFileSync('rsvg-convert', [svgPath, '-f', 'pdf', '-o', pdfPath]);
}

function renderDiagrams() {
	writeFigure('figure-1', svg(1100, 310,
		box(25, 110, 160, 72, 'Sheet series') + arrow(185, 146, 235, 146) + box(240, 110, 190, 72, 'Obtain control\\nembedded or printed', 'amber') + arrow(430, 146, 480, 146) + box(485, 110, 145, 72, 'Warp each sheet') + arrow(630, 146, 680, 146) + box(685, 90, 190, 112, 'Does the check share\\nan assumption\\nwith the warp?', 'amber') + arrow(875, 118, 945, 65) + arrow(875, 174, 945, 230) + svgText(912, 80, 'yes', 'small') + svgText(912, 214, 'no', 'small') + box(950, 30, 140, 72, 'Residual may be\\nblind', 'rose') + box(950, 200, 140, 72, 'Independent\\ndiagnostic', 'green')));
	writeFigure('figure-2', svg(1050, 290,
		box(30, 95, 245, 88, 'Per-sheet evidence\\nframe · diagonals · scale') + box(400, 95, 245, 88, 'Series evidence\\nlattice · occupancy · seams', 'amber') + box(770, 95, 245, 88, 'External evidence\\nmetadata · imagery · cell index', 'green') + arrow(153, 183, 400, 245) + arrow(522, 183, 522, 238) + arrow(892, 183, 645, 245) + box(345, 245, 360, 38, 'No single scope certifies every error class', 'rose')));
	writeFigure('figure-3', svg(1000, 350,
		svgText(80, 38, 'Series coverage (sheets)', 'label') + svgText(350, 82, '0', 'small') + svgText(875, 82, '650', 'small') +
		svgText(170, 135, 'L7014', 'label') + `<rect x="280" y="110" width="570" height="24" fill="#dbeafe"/><rect x="280" y="142" width="419" height="24" fill="#93c5fd"/><rect x="280" y="174" width="411" height="24" fill="#2563eb"/>` + svgText(880, 122, '627 indexed', 'small') + svgText(730, 154, '461 held', 'small') + svgText(722, 186, '452 pipeline', 'small') +
		svgText(155, 255, 'Indochine', 'label') + `<rect x="280" y="230" width="72" height="24" fill="#fef3c7"/><rect x="280" y="262" width="68" height="24" fill="#fbbf24"/><rect x="280" y="294" width="57" height="24" fill="#b45309"/>` + svgText(375, 242, '79 indexed', 'small') + svgText(371, 274, '75 held', 'small') + svgText(360, 306, '62 pipeline', 'small')));
	// Figure 4 · A Lưới 6441-4, AMS Series L7014 (US Army Map Service — US Government work,
	// public domain; scan: Perry-Castañeda Library, UT Austin). Crops written by
	// `gdal_translate -srcwin` from the source GeoPDF.
	writeFigure('figure-4', svg(1100, 620,
		svgText(550, 34, 'What one sheet supplies, and what the check compares', 'label') +
		svgText(268, 70, 'printed corner coordinates', 'small') +
		arrow(232, 84, 142, 132) +
		`<image href="sheet-corner.png" xlink:href="sheet-corner.png" x="40" y="110" width="600" height="360"/>` +
		`<rect x="40" y="110" width="600" height="360" fill="none" stroke="#b3b1a7" stroke-width="1.5"/>` +
		svgText(340, 496, 'A · the neatline corner, and the graticule the sheet prints', 'small') +
		`<image href="sheet-datum.png" xlink:href="sheet-datum.png" x="700" y="180" width="360" height="61"/>` +
		`<rect x="700" y="180" width="360" height="61" fill="none" stroke="#b3b1a7" stroke-width="1.5"/>` +
		svgText(880, 278, 'B · the same sheet declares its datum', 'small') +
		box(700, 330, 360, 140, 'graticule_error compares A against\\ncontrol points read under B.\\nA wrong datum moves both.', 'rose') +
		svgText(550, 556, 'The two operands are not independent: the printed graticule and the control points are', 'small') +
		svgText(550, 581, 'expressed in the same declared datum, so a datum error cancels out of their difference.', 'small')));
	// Figure 5 · free seam distribution, faulty vs corrected. Counts binned from
	// work/l7014/regen/seams-{faulty,fixed}.csv (pdf/pdf rows only), 2026-09-20.
	writeFigure('figure-5', svg(1000, 430, (() => {
		const bins = ['0–10 m', '10–50 m', '50–100 m', '100–300 m', 'over 300 m'];
		const faulty = [377, 149, 2, 92, 97];
		const fixed = [492, 218, 5, 0, 0];
		const max = 492, base = 340, height = 250;
		let out =
			svgText(500, 34, 'Free seam displacement: 717 seams before the fix, 715 after', 'label') +
			`<rect x="322" y="52" width="16" height="16" rx="3" fill="#eb6834"/>` + svgText(392, 61, 'faulty', 'small') +
			`<rect x="462" y="52" width="16" height="16" rx="3" fill="#2a78d6"/>` + svgText(534, 61, 'corrected', 'small') +
			`<line x1="90" y1="${base}" x2="950" y2="${base}" stroke="#b3b1a7" stroke-width="1.5"/>`;
		bins.forEach((label, i) => {
			const cx = 175 + i * 168;
			const hf = Math.round(faulty[i] / max * height);
			const hx = Math.round(fixed[i] / max * height);
			out +=
				`<rect x="${cx - 60}" y="${base - hf}" width="58" height="${hf}" rx="4" fill="#eb6834"/>` +
				`<rect x="${cx + 2}" y="${base - hx}" width="58" height="${hx}" rx="4" fill="#2a78d6"/>` +
				svgText(cx - 31, base - hf - 15, String(faulty[i]), 'small') +
				svgText(cx + 31, base - hx - 15, String(fixed[i]), 'small') +
				svgText(cx, base + 28, label, 'small');
		});
		return out +
			svgText(500, 398, 'Every seam over 100 m disappears under the corrected datum: 189 of them, leaving none.', 'small');
	})()));
	// Figure 6 · the fault in geographic space. Cells and classes from figures/fault-map.json,
	// derived from work/l7014/lattice.json + regen/datum-split.csv, 2026-09-20.
	writeFigure('figure-6', svg(1000, 640, (() => {
		const fm = JSON.parse(readFileSync(`${figuresDir}/fault-map.json`, 'utf8'));
		const lon0 = 101.99, lat0 = 8.24;
		const latPx = 34.0, lonPx = latPx * Math.cos((15.9 * Math.PI) / 180);
		const mx = (lon) => 92 + (lon - lon0) * lonPx;
		const my = (lat) => 588 - (lat - lat0) * latPx;
		const fill = ['#ffffff', '#c9c7be', '#2a78d6', '#eb6834'];
		const edge = ['#dcdad1', '#aeaca2', '#1f5ca3', '#b84d24'];
		let out = svgText(500, 34, 'Where the datum fault fell: 627 cells of AMS Series L7014', 'label');
		for (const [lon, lat, c] of fm.cells) {
			out += `<rect x="${mx(lon).toFixed(1)}" y="${my(lat + 0.25).toFixed(1)}" width="${(0.25 * lonPx).toFixed(1)}" height="${(0.25 * latPx).toFixed(1)}" fill="${fill[c]}" stroke="${edge[c]}" stroke-width="0.4"/>`;
		}
		for (const lat of [10, 15, 20]) {
			out += `<line x1="74" y1="${my(lat).toFixed(1)}" x2="84" y2="${my(lat).toFixed(1)}" stroke="#86847b" stroke-width="1.5"/>` +
				svgText(44, my(lat), `${lat}°N`, 'small');
		}
		// the correctly-placed band, 14–17°N
		out += `<path d="M 352 ${my(17).toFixed(1)} L 366 ${my(17).toFixed(1)} L 366 ${my(14).toFixed(1)} L 352 ${my(14).toFixed(1)}" fill="none" stroke="#0b0b0b" stroke-width="1.8"/>` +
			svgText(470, my(15.5) - 12, 'no sheet between', 'small') +
			svgText(470, my(15.5) + 11, '14°N and 17°N took', 'small') +
			svgText(470, my(15.5) + 34, 'the faulty route', 'small');
		const legend = [
			[3, '269 warped and displaced', '395–528 m, median 455 m'],
			[2, '168 warped and placed', 'displacement under 100 m'],
			[1, '73 held but not warped', 'no usable GCPs, or off its cell'],
			[0, '117 cell not held', 'no sheet acquired']
		];
		legend.forEach(([c, head, sub], i) => {
			const y = 120 + i * 78;
			out += `<rect x="620" y="${y}" width="26" height="26" rx="3" fill="${fill[c]}" stroke="${edge[c]}" stroke-width="1.5"/>` +
				`<text x="664" y="${y + 13}" class="label" style="text-anchor:start">${esc(head)}</text>` +
				`<text x="664" y="${y + 38}" class="small" style="text-anchor:start">${esc(sub)}</text>`;
		});
		out += `<line x1="620" y1="448" x2="960" y2="448" stroke="#b3b1a7" stroke-width="1.5"/>` +
			`<text x="620" y="478" class="small" style="text-anchor:start">627 cells indexed</text>` +
			`<text x="620" y="504" class="small" style="text-anchor:start">510 GeoPDFs held = 117 short of the index</text>` +
			`<text x="620" y="530" class="small" style="text-anchor:start">437 warped = 168 placed + 269 displaced</text>` +
			`<text x="620" y="556" class="small" style="text-anchor:start">452 published in the mosaic (hand-maintained)</text>`;
		return out;
	})()));
	writeFigure('figure-7', svg(1000, 345,
		svgText(500, 35, 'Dry-run fit: sheets on their cell, faulty vs corrected', 'label') +
		svgText(115, 122, 'faulty pass\\n437 warped', 'small') +
		`<rect x="230" y="95" width="243" height="70" rx="4" class="box green"/>` +
		`<rect x="473" y="95" width="417" height="70" rx="4" class="box rose"/>` +
		svgText(352, 130, '161 on cell', 'label') +
		svgText(682, 130, '276 over 150 m off', 'label') +
		svgText(115, 227, 'corrected pass\\n436 warped', 'small') +
		`<rect x="230" y="200" width="657" height="70" rx="4" class="box green"/>` +
		`<rect x="887" y="200" width="3" height="70" class="box rose"/>` +
		svgText(559, 235, '434 on cell', 'label') +
		svgText(906, 235, '2', 'small') +
		svgText(500, 302, 'Median miss among on-cell sheets: 11 m → 10 m; worst on-cell 50 m → 95 m as 273 sheets join that population.\\nThe correction moves displaced sheets onto their cells rather than improving sheets already on them.', 'small')));	writeFigure('figure-8', svg(1100, 310,
		box(25, 110, 190, 72, 'Viewer requests\\nwidth-only size') + arrow(215, 146, 290, 146) + box(295, 96, 210, 100, 'Exact generated\\nsize segment?', 'amber') + arrow(505, 119, 590, 65) + arrow(505, 174, 590, 235) + svgText(550, 77, 'full resolution', 'small') + svgText(550, 220, 'lower pyramid level', 'small') + box(600, 30, 150, 72, 'Yes: 200', 'green') + box(600, 200, 150, 72, 'Often no: 404', 'rose') + box(800, 110, 175, 72, 'Tile-key audit\\nkeys in object store', 'blue') + arrow(800, 146, 750, 225) + arrow(975, 146, 1040, 146) + box(1045, 110, 50, 72, '✓', 'green')));
	writeFigure('figure-9', svg(1100, 250,
		box(25, 85, 190, 72, 'Institutional scans\\nIIIF or catalogue link') + arrow(215, 121, 285, 121) + box(290, 85, 190, 72, 'Derived control points\\nand annotations', 'amber') + arrow(480, 121, 550, 121) + box(555, 85, 190, 72, 'Verification outputs\\nand figures ledger') + arrow(745, 121, 815, 121) + box(820, 85, 230, 72, 'Versioned Zenodo release\\nCC-BY-4.0', 'green') + arrow(120, 157, 930, 215, true) + svgText(525, 205, 'scans not redistributed', 'small')));

}

renderDiagrams();

function inline(sourceText) {
	const tokens = [];
	const keep = (tex) => `@@TOKEN${tokens.push(tex) - 1}@@`;
	let value = sourceText
		.replace(/`([^`]+)`/g, (_, code) => keep(code === '∅' ? '\\ensuremath{\\varnothing}' : `\\texttt{\\detokenize{${code}}}`))
		.replace(/https?:\/\/\S+/g, (url) => keep(`\\url{${url}}`))
		.replace(/✓/g, keep('\\ensuremath{\\checkmark}'))
		.replace(/∅/g, keep('\\ensuremath{\\varnothing}'));
	value = value
		.replace(/\\/g, '\\textbackslash{}')
		.replace(/([#$%&_{}])/g, '\\$1')
		.replace(/~/g, '\\textasciitilde{}')
		.replace(/\^/g, '\\textasciicircum{}');
	value = value.replace(/\*\*(.+?)\*\*/g, '\\textbf{$1}').replace(/\*(.+?)\*/g, '\\emph{$1}');
	return value.replace(/@@TOKEN(\d+)@@/g, (_, index) => tokens[Number(index)]);
}

function table(rows) {
	const cells = rows.map((row) => row.slice(1, -1).split('|').map((cell) => cell.trim()));
	const header = cells.shift();
	cells.shift(); // Markdown separator
	const columns = header.length;
	const landscape = columns > 4;
	// A landscape table is laid across the page height, and its trailing columns are single marks.
	const basis = landscape ? '\\textheight' : '\\linewidth';
	const left = (share) => `>{\\raggedright\\arraybackslash}p{${share.toFixed(3)}${basis}}`;
	const spec = landscape
		? left(0.22) + left(0.09) + Array.from({ length: columns - 2 }, () => `>{\\centering\\arraybackslash}p{${(0.69 / (columns - 2)).toFixed(3)}${basis}}`).join('')
		: Array.from({ length: columns }, () => left(0.94 / columns)).join('');
	const row = (items) => items.map(inline).join(' & ') + ' \\\\ \\hline';
	return [
		landscape ? '\\begin{landscape}' : '',
		'\\begin{center}',
		landscape ? '\\footnotesize' : '\\small',
		`\\begin{longtable}{|${spec}|}`,
		'\\hline',
		row(header),
		'\\endfirsthead',
		'\\hline',
		row(header),
		'\\endhead',
		...cells.map(row),
		'\\end{longtable}',
		'\\end{center}',
		landscape ? '\\end{landscape}' : ''
	].filter(Boolean).join('\n');
}

const lines = readFileSync(source, 'utf8').split(/\r?\n/);
const out = [];
let paragraph = [];
let diagramNumber = 0;
const flush = () => {
	if (paragraph.length) out.push(`${inline(paragraph.join(' ').trim())}\n`);
	paragraph = [];
};

for (let index = 0; index < lines.length; index += 1) {
	const line = lines[index];
	if (/^<!--/.test(line)) {
		while (index < lines.length && !lines[index].includes('-->')) index += 1;
		continue;
	}
	const image = line.match(/^!\[(.*)\]\(([^)]+)\)$/);
	if (image) {
		flush();
		out.push(`\\begin{figure}[htbp]\\centering\\includegraphics[width=0.92\\linewidth]{${image[2]}}\\end{figure}\n`);
		continue;
	}
	if (line.startsWith('```')) {
		flush();
		const language = line.slice(3).trim();
		const code = [];
		while (++index < lines.length && !lines[index].startsWith('```')) code.push(lines[index]);
		if (language === 'mermaid') {
			diagramNumber += 1;
			out.push(`\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=\\linewidth]{figures/figure-${[1, 2, 8, 9][diagramNumber - 1]}.pdf}\n\\end{figure}\n`);
		} else out.push(`\\begin{verbatim}\n${code.join('\n')}\n\\end{verbatim}\n`);
		continue;
	}
	if (/^\|/.test(line)) {
		flush();
		const rows = [line];
		while (index + 1 < lines.length && /^\|/.test(lines[index + 1])) rows.push(lines[++index]);
		out.push(`${table(rows)}\n`);
		continue;
	}
	if (/^---+$/.test(line.trim())) {
		flush();
		out.push('\\bigskip\\hrule\\bigskip\n');
		continue;
	}
	if (!line.trim()) {
		flush();
		continue;
	}
	if (/^>\s?/.test(line)) {
		flush();
		const quote = [line.replace(/^>\s?/, '')];
		while (index + 1 < lines.length && /^>\s?/.test(lines[index + 1])) quote.push(lines[++index].replace(/^>\s?/, ''));
		out.push(`\\begin{quote}\\itshape\n${inline(quote.join(' ').trim())}\n\\end{quote}\n`);
		continue;
	}
	const heading = line.match(/^(#{1,3})\s+(.*)$/);
	if (heading) {
		flush();
		const command = ['\\section', '\\subsection'][heading[1].length - 2] || '\\subsubsection';
		const title = inline(heading[2].replace(/^§?\d+(?:\.\d+)?\s+/, ''));
		// The abstract is front matter, so numbering starts at the introduction.
		out.push(`${command}${title === 'Abstract' ? '*' : ''}{${title}}\n`);
		continue;
	}
	const item = line.match(/^-\s+(.*)$/);
	if (item) {
		flush();
		const items = [item[1]];
		// An entry wrapped onto an indented line continues the item; it is not a new paragraph.
		while (index + 1 < lines.length && /^(?:-\s+|\s+\S)/.test(lines[index + 1])) {
			const next = lines[++index];
			if (/^-\s+/.test(next)) items.push(next.replace(/^-\s+/, ''));
			else items[items.length - 1] += ` ${next.trim()}`;
		}
		out.push(`\\begin{itemize}\n${items.map((entry) => `\\item ${inline(entry)}`).join('\n')}\n\\end{itemize}\n`);
		continue;
	}
	paragraph.push(line);
}
flush();

const preamble = String.raw`\documentclass[11pt,a4paper]{article}
\usepackage[a4paper,margin=26mm]{geometry}
\usepackage{microtype}
\usepackage{booktabs,longtable,array}
\usepackage{pdflscape}
\usepackage{amssymb}
\usepackage{graphicx}
\usepackage{caption}
\usepackage{xurl}
\usepackage{hyperref}
\hypersetup{colorlinks=true,linkcolor=black,urlcolor=blue,citecolor=black,pdftitle={Blind by construction}}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.7em}
\renewcommand{\arraystretch}{1.2}
\setlength{\emergencystretch}{3em}
\begin{document}
\begin{center}
{\small\itshape This is a non-peer reviewed preprint submitted to EarthArXiv.\\
This preprint has not been submitted to a journal for peer review.\par}
\end{center}
\vspace{1.5em}
\begin{center}
{\LARGE\bfseries Blind by construction: verifying a georeferenced map series when the check shares the error\par}
\vspace{0.5em}
{\large Two colonial map series of Vietnam, 514 sheets\par}
\vspace{1.2em}
{\large Tue Quang Le\par}
\vspace{0.3em}
{\small \href{https://orcid.org/0009-0006-5863-6011}{orcid.org/0009-0006-5863-6011}\par}
{\small Independent researcher, Ho Chi Minh City, Vietnam\par}
{\small \href{mailto:lequangtuevn@gmail.com}{lequangtuevn@gmail.com} · \href{https://maparchive.vn}{maparchive.vn}\par}
\vspace{1em}
{\small Preprint — 20 September 2026\par}
\end{center}
`;

const body = out.slice(2).join('\n'); // Title and subtitle are supplied by the typeset title block.
writeFileSync(output, `${preamble}\n${body}\n\\end{document}\n`);
