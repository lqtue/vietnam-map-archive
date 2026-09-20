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
	// Explanatory geometry is schematic; measured results are labelled separately.
	const text = (x, y, value, css = 'small') => `<text x="${x}" y="${y}" class="${css}" style="text-anchor:start">${esc(value)}</text>`;
	const rect = (x, y, w, h, fill, stroke = fill, dash = '') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" stroke="${stroke}" stroke-width="2" stroke-dasharray="${dash}"/>`;
	const panel = (x, title) => rect(x, 65, 450, 265, '#f8fafc', '#e2e8f0') + text(x + 20, 98, title, 'label');
	writeFigure('figure-1', svg(1000, 440,
		svgText(500, 30, 'A shared error can leave the check unchanged', 'label') +
		panel(30, 'A · Before a shared shift') + panel(520, 'B · After a shared shift') +
		text(55, 150, 'Control') + text(55, 215, 'Graticule') +
		text(545, 150, 'Control') + text(545, 215, 'Graticule') +
		`<path d="M 250 125 V 240 M 740 125 V 240" stroke="#94a3b8" stroke-dasharray="5 5"/>` +
		`<circle cx="250" cy="145" r="9" fill="#2a78d6"/><circle cx="250" cy="210" r="9" fill="#2a78d6"/>` +
		arrow(740, 145, 870, 145) + arrow(740, 210, 870, 210) +
		`<circle cx="870" cy="145" r="9" fill="#eb6834"/><circle cx="870" cy="210" r="9" fill="#eb6834"/>` +
		text(55, 290, 'Their difference is zero.') + text(545, 290, 'Both move by the same amount: still zero.') +
		svgText(500, 367, '(control + shift) − (graticule + shift) = control − graticule', 'label') +
		svgText(500, 403, 'Measured in L7014: all 269 displaced sheets passed; median displacement 455 m.', 'small')));
	writeFigure('figure-2', svg(1000, 440, (() => {
		let out = svgText(500, 30, 'A seam detects a difference between neighbours', 'label');
		const cases = [
			['A · Neither sheet shifted', 0, 0, 'The edges meet.'],
			['B · Only one sheet shifted', 0, 30, 'The gap exposes the fault.'],
			['C · Both shifted together', 30, 30, 'The edges still meet.']
		];
		cases.forEach(([title, da, db, note], i) => {
			const x = 25 + i * 330;
			out += text(x, 85, title, 'label');
			out += rect(x + 30, 130, 110, 125, 'none', '#94a3b8', '5 5') + rect(x + 140, 130, 110, 125, 'none', '#94a3b8', '5 5');
			out += rect(x + 30 + da, 145, 110, 95, da ? '#ffe3d6' : '#deebfc', da ? '#eb6834' : '#2a78d6');
			out += rect(x + 140 + db, 145, 110, 95, db ? '#ffe3d6' : '#deebfc', db ? '#eb6834' : '#2a78d6');
			out += text(x + 30, 292, note);
		});
		return out + svgText(500, 350, 'Dashed outlines: unshifted cells. Coloured blocks: placed sheets. Schematic, not to scale.', 'small') +
			svgText(500, 395, 'A common shift needs an outside reference. An enforced seam cannot serve as this test.', 'label');
	})()));
	writeFigure('figure-3', svg(1000, 410,
		svgText(500, 30, 'Which population answers which question?', 'label') +
		text(35, 85, 'L7014 · controlled reproduction', 'label') + text(560, 85, 'Indochine · distinct audits', 'label') +
		text(35, 132, '627 indexed cells') + arrow(215, 125, 255, 125) + text(270, 132, '510 GeoPDFs held') +
		text(35, 183, '437 warped in faulty pass') + text(35, 219, '269 displaced + 168 placed') +
		text(35, 270, '436 warped in corrected pass') + text(35, 306, '434 on cell + 2 over 150 m off') +
		text(560, 132, '79 indexed cells / 75 held') + text(560, 183, '62 pipeline-georeferenced sheets') +
		text(560, 234, '58 sheets read for the lattice check') + text(560, 285, '83 image sources in the tile audit') +
		rect(35, 335, 930, 48, '#f1f5f9') +
		text(50, 364, '514 = recorded processing total (452 + 62); 452 is not a verified live manifest count.')));
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
		box(700, 330, 360, 140, 'graticule_error compares A against\\ncontrol points read under B.\\nA shared datum error is invisible.', 'rose') +
		svgText(550, 556, 'The two operands are not independent: the printed graticule and the control points are', 'small') +
		svgText(550, 581, 'expressed in the same declared datum, so a datum error cancels out of their difference.', 'small')));
	// Figure 5 · free seam distribution, faulty vs corrected. Counts binned from
	// work/l7014/regen/seams-{faulty,fixed}.csv (pdf/pdf rows only), 2026-09-20.
	writeFigure('figure-5', svg(1000, 430, (() => {
		const bins = ['0–10 m', '10–50 m', '50–100 m', '100–300 m', 'over 300 m'];
		const faulty = [377, 149, 2, 92, 97];
		const fixed = [492, 218, 5, 0, 0];
		const max = 492, base = 340, height = 230;
		let out =
			`<rect x="612" y="85" width="330" height="260" fill="#fff3ec"/>` +
			svgText(500, 34, 'A low median conceals 189 seams over 100 m', 'label') +
			svgText(777, 105, 'Large-displacement tail', 'small') +
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
			svgText(500, 398, 'Seams over 100 m: 189 / 717 before; 0 / 715 after. Separate builds, not matched pairs.', 'small');
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
			[0, '117 cells not held', 'no sheet acquired']
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
	writeFigure('figure-7', svg(1000, 400, (() => {
		let out = svgText(500, 30, 'The correction changes how many sheets reach their cell', 'label');
		for (const [y, name, total, placed, off] of [[115, 'Faulty', 437, 161, 276], [240, 'Corrected', 436, 434, 2]]) {
			const w = 700 * placed / 437, bad = 700 * off / 437;
			out += text(30, y, name, 'label') + text(30, y + 27, `${total} warped`);
			out += rect(215, y - 25, w, 48, '#2a78d6') + rect(215 + w, y - 25, bad, 48, '#eb6834');
			out += text(215, y + 54, `${placed} on cell`);
			out += text(610, y + 54, `${off} more than 150 m off cell`);
		}
		return out + svgText(500, 355, 'Separate dry-run builds. One fewer sheet warps after correction. Public mosaic not rebuilt.', 'small');
	})()));
	writeFigure('figure-8', svg(1000, 330,
		svgText(500, 30, 'A full-resolution success misses the failing zoom level', 'label') +
		text(35, 95, 'Full resolution', 'label') + text(35, 195, 'One level below overview', 'label') +
		rect(350, 70, 600, 40, '#deebfc') + text(350, 140, '0% of tiles fail') +
		rect(350, 170, 600, 40, '#deebfc') + rect(350, 170, 600 * 0.586, 40, '#eb6834') +
		text(350, 240, '58.6% of tiles fail across the 83-image-source survey') +
		svgText(500, 295, 'Requested width-only size → stored explicit width,height key: audit the actual tile requests.', 'small')));
	writeFigure('figure-9', svg(1000, 330,
		svgText(500, 30, 'Keep the evidence attached to the build it describes', 'label') +
		text(35, 95, 'PUBLIC ARCHIVE', 'label') + text(365, 95, 'LOCAL REPRODUCTION', 'label') + text(695, 95, 'PLANNED DEPOSIT', 'label') +
		text(35, 145, 'l7014-20260913') + text(35, 180, 'Pixels served; manifest 404') + text(35, 215, '452 is an unverified constant') +
		text(365, 145, 'Faulty and corrected runs') + text(365, 180, 'Logs, seams and cell checks') + text(365, 215, 'Evidence for the correction') +
		text(695, 145, 'Versioned derived data + code') + text(695, 180, 'Zenodo DOI not yet minted') + text(695, 215, 'Scans remain at institutions') +
		svgText(500, 285, 'A successful local correction does not establish what a public viewer receives.', 'label')));


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
let pendingCaption = null;
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
	if (/^\*\*Figure \d+ — /.test(line)) {
		flush();
		const caption = [line];
		while (index + 1 < lines.length && lines[index + 1].trim()) caption.push(lines[++index]);
		pendingCaption = caption.join(' ').replace(/\*\*/g, '').replace(/^Figure \d+ — /, '');
		pendingCaption = pendingCaption[0].toUpperCase() + pendingCaption.slice(1);
		continue;
	}
	const image = line.match(/^!\[(.*)\]\(([^)]+)\)$/);
	if (image) {
		flush();
		if (!pendingCaption) throw new Error(`Figure missing caption: ${image[2]}`);
		out.push(`\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=\\linewidth]{${image[2]}}\n\\caption{${inline(pendingCaption)}}\n\\end{figure}\n`);
		pendingCaption = null;
		continue;
	}
	if (line.startsWith('```')) {
		flush();
		const language = line.slice(3).trim();
		const code = [];
		while (++index < lines.length && !lines[index].startsWith('```')) code.push(lines[index]);
		if (language === 'mermaid') throw new Error('Use an explicit figure path for paper diagrams.');
		out.push(`\\begin{verbatim}\n${code.join('\n')}\n\\end{verbatim}\n`);
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
\usepackage[section]{placeins}
\captionsetup{font=small,labelfont=bf}
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
{\large Two historical map series of Vietnam\par}
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
