import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const source = 'docs/paper/draft.md';
const output = 'docs/paper/blind-by-construction.tex';
const figuresDir = 'docs/paper/figures';

const esc = (value) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const svgText = (x, y, text, css = 'label') => text.split('\\n').map((line, i) => `<text x="${x}" y="${y + i * 23}" class="${css}">${esc(line)}</text>`).join('');
const box = (x, y, width, height, text, tone = 'blue') => `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="12" class="box ${tone}"/>${svgText(x + width / 2, y + height / 2 - (text.split('\\n').length - 1) * 11 + 7, text)}`;
const arrow = (x1, y1, x2, y2, dashed = false) => `<path d="M ${x1} ${y1} L ${x2} ${y2}" class="arrow${dashed ? ' dashed' : ''}" marker-end="url(#arrow)"/>`;
const svg = (width, height, content) => `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">\n<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#334155"/></marker><style>.box{stroke-width:2}.blue{fill:#e0f2fe;stroke:#0369a1}.amber{fill:#fef3c7;stroke:#b45309}.green{fill:#dcfce7;stroke:#15803d}.rose{fill:#ffe4e6;stroke:#be123c}.label{font:600 18px Arial,sans-serif;fill:#0f172a;text-anchor:middle;dominant-baseline:middle}.small{font:16px Arial,sans-serif;fill:#475569;text-anchor:middle}.arrow{stroke:#334155;stroke-width:2.5;fill:none}.dashed{stroke-dasharray:7 6}</style></defs>\n${content}\n</svg>`;

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
	writeFigure('figure-13', svg(1100, 310,
		box(25, 110, 190, 72, 'Viewer requests\\nwidth-only size') + arrow(215, 146, 290, 146) + box(295, 96, 210, 100, 'Exact generated\\nsize segment?', 'amber') + arrow(505, 119, 590, 65) + arrow(505, 174, 590, 235) + svgText(550, 77, 'full resolution', 'small') + svgText(550, 220, 'lower pyramid level', 'small') + box(600, 30, 150, 72, 'Yes: 200', 'green') + box(600, 200, 150, 72, 'Often no: 404', 'rose') + box(800, 110, 175, 72, 'Tile-key audit\\nkeys in object store', 'blue') + arrow(800, 146, 750, 225) + arrow(975, 146, 1040, 146) + box(1045, 110, 50, 72, '✓', 'green')));
	writeFigure('figure-14', svg(1100, 250,
		box(25, 85, 190, 72, 'Institutional scans\\nIIIF or catalogue link') + arrow(215, 121, 285, 121) + box(290, 85, 190, 72, 'Derived control points\\nand annotations', 'amber') + arrow(480, 121, 550, 121) + box(555, 85, 190, 72, 'Verification outputs\\nand figures ledger') + arrow(745, 121, 815, 121) + box(820, 85, 230, 72, 'Versioned Zenodo release\\nCC-BY-4.0', 'green') + arrow(120, 157, 930, 215, true) + svgText(525, 205, 'scans not redistributed', 'small')));
	writeFigure('figure-3', svg(1000, 350,
		svgText(80, 38, 'Series coverage (sheets)', 'label') + svgText(350, 82, '0', 'small') + svgText(875, 82, '650', 'small') +
		svgText(170, 135, 'L7014', 'label') + `<rect x="280" y="110" width="570" height="24" fill="#dbeafe"/><rect x="280" y="142" width="419" height="24" fill="#93c5fd"/><rect x="280" y="174" width="411" height="24" fill="#2563eb"/>` + svgText(880, 122, '627 indexed', 'small') + svgText(730, 154, '461 held', 'small') + svgText(722, 186, '452 pipeline', 'small') +
		svgText(155, 255, 'Indochine', 'label') + `<rect x="280" y="230" width="72" height="24" fill="#fef3c7"/><rect x="280" y="262" width="68" height="24" fill="#fbbf24"/><rect x="280" y="294" width="57" height="24" fill="#b45309"/>` + svgText(375, 242, '79 indexed', 'small') + svgText(371, 274, '75 held', 'small') + svgText(360, 306, '62 pipeline', 'small')));
	writeFigure('figure-4', svg(1000, 300,
		svgText(500, 38, 'Free-seam census: the denominator makes the anomaly legible', 'label') +
		box(60, 105, 240, 105, '750\\nadjacent seams measured', 'blue') + arrow(300, 157, 365, 157) + box(375, 105, 240, 105, '56\\nseams over 300 m', 'amber') + arrow(615, 157, 680, 157) + box(690, 105, 250, 105, '33\\nhand-to-mosaic seams\\n447–504 m', 'rose')));
	writeFigure('figure-5', svg(1000, 335,
		svgText(500, 35, 'Dry-run cell miss after explicit datum transformation', 'label') + `<line x1="130" y1="275" x2="900" y2="275" class="arrow"/>` + `<rect x="210" y="70" width="145" height="205" fill="#be123c"/><rect x="510" y="272" width="145" height="3" fill="#15803d"/><rect x="730" y="270" width="52" height="5" fill="#0369a1"/><rect x="805" y="220" width="52" height="55" fill="#0369a1"/>` + svgText(282, 55, '430 m', 'label') + svgText(582, 250, '0 m', 'label') + svgText(756, 247, '9 m', 'label') + svgText(831, 202, '115 m', 'label') + svgText(282, 305, 'median before', 'small') + svgText(582, 305, 'median after', 'small') + svgText(756, 305, 'p95 after', 'small') + svgText(831, 305, 'max after', 'small')));
}

renderDiagrams();

function inline(sourceText) {
	const tokens = [];
	const keep = (tex) => `@@TOKEN${tokens.push(tex) - 1}@@`;
	let value = sourceText
		.replace(/`([^`]+)`/g, (_, code) => keep(code === '∅' ? '\\ensuremath{\\varnothing}' : `\\texttt{\\detokenize{${code}}}`))
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
	const width = (0.94 / columns).toFixed(3);
	const spec = Array.from({ length: columns }, () => `>{\\raggedright\\arraybackslash}p{${width}\\linewidth}`).join('');
	const row = (items) => items.map(inline).join(' & ') + ' \\\\ \\hline';
	const landscape = columns > 4;
	return [
		landscape ? '\\begin{landscape}' : '',
		'\\begin{center}',
		'\\small',
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
			out.push(`\\begin{figure}[htbp]\n\\centering\n\\includegraphics[width=\\linewidth]{figures/figure-${[1, 2, 13, 14][diagramNumber - 1]}.pdf}\n\\end{figure}\n`);
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
		out.push(`${command}{${inline(heading[2].replace(/^§?\d+(?:\.\d+)?\s+/, ''))}}\n`);
		continue;
	}
	const item = line.match(/^-\s+(.*)$/);
	if (item) {
		flush();
		const items = [item[1]];
		while (index + 1 < lines.length && /^-\s+/.test(lines[index + 1])) items.push(lines[++index].replace(/^-\s+/, ''));
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
\usepackage{hyperref}
\hypersetup{colorlinks=true,linkcolor=black,urlcolor=blue,citecolor=black,pdftitle={Blind by construction}}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.7em}
\renewcommand{\arraystretch}{1.2}
\setlength{\emergencystretch}{3em}
\begin{document}
\begin{center}
{\LARGE\bfseries Blind by construction: verifying a georeferenced map series when the check shares the error\par}
\vspace{0.5em}
{\large Two colonial map series of Vietnam, 514 sheets\par}
\vspace{1em}
{\small Draft — 20 September 2026\par}
\end{center}
`;

const body = out.slice(2).join('\n'); // Title and subtitle are supplied by the typeset title block.
writeFileSync(output, `${preamble}\n${body}\n\\end{document}\n`);
