const fs = require("fs"), path = require("path");

const dp = path.join(__dirname, "node_modules", "docx", "dist", "index.cjs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun,
  AlignmentType, BorderStyle, WidthType, ShadingType,
  HeadingLevel, Table, TableRow, TableCell, TextDirection,
  VerticalAlign, PageBreak
} = require(dp);

// === helpers ===
const t = (s) => s; // text identity

function tdBox(w, content, opts = {}) {
  const b = { style: BorderStyle.SINGLE, size: opts.borderSize || 4, color: opts.borderColor || "B8860B" };
  return new TableCell({
    borders: { top: b, bottom: b, left: b, right: b },
    width: { size: w, type: WidthType.DXA },
    margins: { top: 80, bottom: 40, left: 80, right: 80 },
    verticalAlign: VerticalAlign.TOP,
    children: content
  });
}

function vPara(text, opts = {}) {
  return new Paragraph({
    textDirection: TextDirection.TOP_TO_BOTTOM_RIGHT_TO_LEFT,
    spacing: { before: opts.before || 0, after: opts.after || 80, line: 320 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: opts.font || "SimSun", size: opts.size || 22, bold: opts.bold || false, color: "1A1A1A" })]
  });
}

function vParaL(text, opts = {}) {
  return new Paragraph({
    textDirection: TextDirection.TOP_TO_BOTTOM_RIGHT_TO_LEFT,
    spacing: { before: opts.before || 0, after: opts.after || 60, line: 300 },
    children: [new TextRun({ text, font: opts.font || "SimSun", size: opts.size || 20, color: "333333" })]
  });
}

function emptyVPara() {
  return new Paragraph({ textDirection: TextDirection.TOP_TO_BOTTOM_RIGHT_TO_LEFT, spacing: { line: 200 }, children: [new TextRun({ text: "　", size: 18, font: "SimSun" })] });
}

function vLabel(label) {
  return new Paragraph({
    textDirection: TextDirection.TOP_TO_BOTTOM_RIGHT_TO_LEFT,
    spacing: { before: 60, after: 40 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: label, font: "SimHei", size: 26, bold: true, color: "8B0000" })]
  });
}

function vTitle(text) {
  return new Paragraph({
    textDirection: TextDirection.TOP_TO_BOTTOM_RIGHT_TO_LEFT,
    spacing: { before: 0, after: 200 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: "SimHei", size: 28, bold: true, color: "8B0000" })]
  });
}

const outerB = { style: BorderStyle.SINGLE, size: 12, color: "8B4513" };
const outerBorders = { top: outerB, bottom: outerB, left: outerB, right: outerB };

// Table columns (physical left-to-right, reading right-to-left)
// Col7=Title, Col6=福主, Col5=古取, Col4=古课, Col3=古动, Col2=古课之, Col1=碑, Col0=署名
const colW = 1100; // ~0.76 inch per column
const cols = 8;

const row = new TableRow({
  height: { value: 13000, rule: "atLeast" },
  children: [
    // Col 0: 署名 (leftmost visually)
    tdBox(colW, [
      emptyVPara(), emptyVPara(), emptyVPara(), emptyVPara(), emptyVPara(), emptyVPara(),
      vParaL("高明", { size: 18 }),
      vParaL("评", { size: 18 }),
      emptyVPara(), emptyVPara(),
      vParaL("地", { size: 16 }),
      vParaL("课", { size: 16 }),
      vParaL("师", { size: 16 })
    ]),
    // Col 1: 碑
    tdBox(colW, [
      vLabel("碑"),
      vParaL("乙未", { before: 80 }),
      vParaL("吉"),
      emptyVPara(),
      vParaL("此碑用松、"),
      vParaL("紫气东来、"),
      vParaL("百福深臻"),
      emptyVPara(),
      vParaL("万祥云集木"),
      vParaL("福寿康宁"),
      emptyVPara(),
      vParaL("了财多旺"),
      vParaL("发福久远"),
      vParaL("可喜可贺")
    ]),
    // Col 2: 古课之
    tdBox(colW, [
      vLabel("古　之"),
      vLabel("　课　"),
      emptyVPara(),
      vParaL("亥年", { before: 40 }),
      vParaL("择取"),
      vParaL("丙午年"),
      vParaL("农历六月"),
      vParaL("十八日"),
      vParaL("未时"),
      emptyVPara(),
      vParaL("乙未"),
      vParaL("即是下午"),
      vParaL("二点半钟"),
      vParaL("立碑大")
    ]),
    // Col 3: 古动
    tdBox(colW, [
      vLabel("古"),
      vLabel("动"),
      emptyVPara(),
      vParaL("亥年", { before: 40 }),
      vParaL("择取"),
      vParaL("丙午年"),
      vParaL("农历六月"),
      vParaL("廿四日未时"),
      emptyVPara(),
      vParaL("乙未"),
      vParaL("即是十一点"),
      vParaL("半钟"),
      vParaL("动工大吉"),
      emptyVPara(),
      vLabel("工"),
      vParaL("全寅"),
      vParaL("丁未")
    ]),
    // Col 4: 古课
    tdBox(colW, [
      vLabel("古"),
      vLabel("课"),
      emptyVPara(), emptyVPara(), emptyVPara(),
      vParaL("全寅", { before: 100 }),
      vParaL("　吉　", { size: 22 }),
      emptyVPara(), emptyVPara(),
      vParaL("灵生寅"),
      vParaL("　吉　", { size: 22 })
    ]),
    // Col 5: 古取
    tdBox(colW, [
      vLabel("古"),
      vLabel("取"),
      emptyVPara(),
      vParaL("历年", { before: 40 }),
      vParaL("择取"),
      vParaL("丙午年"),
      vParaL("农历六月"),
      vParaL("廿四日"),
      vParaL("寅时"),
      emptyVPara(),
      vParaL("乙未"),
      vParaL("即是"),
      vParaL("早上四"),
      vParaL("点半钟"),
      vParaL("取灵大")
    ]),
    // Col 6: 福主
    tdBox(colW, [
      emptyVPara(), emptyVPara(), emptyVPara(),
      vParaL("福主：", { before: 100, size: 20 }),
      vParaL("众多，", { size: 20 }),
      vParaL("年度大吉", { size: 20 }),
      emptyVPara(), emptyVPara(), emptyVPara(), emptyVPara()
    ]),
    // Col 7: 标题 (rightmost visually)
    tdBox(colW, [
      emptyVPara(), emptyVPara(),
      vTitle("福"),
      vTitle("地"),
      vTitle("坐"),
      vTitle("辰"),
      vTitle("向"),
      vTitle("戌"),
      vTitle("兼"),
      vTitle("巽"),
      vTitle("乾"),
      vTitle("吉"),
      vTitle("度"),
      vTitle("分"),
      vTitle("金"),
      emptyVPara(),
      vTitle("修"),
      vTitle("改"),
      vTitle("古"),
      vTitle("事")
    ])
  ]
});

// Wrap table in outer decorative border cell
const innerTable = new Table({
  width: { size: colW * cols, type: WidthType.DXA },
  columnWidths: Array(cols).fill(colW),
  rows: [row]
});

const wrapperCell = new TableCell({
  borders: outerBorders,
  margins: { top: 120, bottom: 120, left: 120, right: 120 },
  width: { size: 9300, type: WidthType.DXA },
  children: [innerTable]
});

const wrapperTable = new Table({
  width: { size: 9026, type: WidthType.DXA },
  columnWidths: [9300],
  rows: [new TableRow({ children: [wrapperCell] })]
});

// ===== Document =====
const doc = new Document({
  styles: {
    default: { document: { run: { font: "SimSun", size: 20 } } }
  },
  sections: [
    // Page 1: Original image
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 720, right: 720, bottom: 720, left: 720 }
        }
      },
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: "【原文图片 · 参考对照】", size: 20, font: "SimHei", color: "888888" })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new ImageRun({
              type: "jpg",
              data: Buffer.from(fs.readFileSync(path.join(__dirname, "fengshui_doc.jpg"))),
              transformation: { width: 560, height: 380 },
              altText: { title: "原文", description: "手写风水文书原图", name: "Original" }
            })
          ]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 160 },
          children: [new TextRun({ text: "▲ 高清原图（粉色底·手写竖排）", size: 18, font: "SimSun", color: "999999", italics: true })]
        })
      ]
    },
    // Page 2: Editable vertical re-creation
    {
      properties: {
        page: {
          size: { width: 16838, height: 11906, orientation: "landscape" },
          margin: { top: 720, right: 720, bottom: 720, left: 720 }
        }
      },
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: "【可编辑竖排版 · 照原图复刻】", size: 20, font: "SimHei", color: "8B4513" })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 300 },
          children: [new TextRun({ text: "↑ 阅读方向：从右到左（最右列为标题，最左列为署名）", size: 16, font: "SimSun", color: "666666" })]
        }),
        wrapperTable
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buf => {
  const outPath = path.join(__dirname, "fengshui_doc.docx");
  fs.writeFileSync(outPath, buf);
  console.log("DONE: " + outPath + " (" + (buf.length / 1024).toFixed(0) + " KB)");
}).catch(err => {
  console.error("FAIL:", err.message);
  process.exit(1);
});