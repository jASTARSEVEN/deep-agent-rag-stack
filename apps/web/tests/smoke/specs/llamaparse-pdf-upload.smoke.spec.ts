/** Compose smoke 測試 LlamaParse PDF upload 流程，入口固定走 Caddy。 */

import { expect, test } from "@playwright/test";

import { createAndOpenSmokeArea, loginViaPublicKeycloak } from "../support/publicEntry";


/** 可提供給 LlamaParse smoke 的最小 PDF 測試樣本。 */
const MINIMAL_TEXT_PDF = Buffer.from(`%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 73 >>
stream
BT
/F1 18 Tf
50 100 Td
(Deep Agent PDF LlamaParse smoke sample) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000248 00000 n 
0000000371 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
441
%%EOF
`, "utf-8");


test("有設定 LlamaParse 時應可完成 gated PDF smoke", async ({ page }) => {
  test.skip(
    !process.env.LLAMAPARSE_API_KEY || process.env.PDF_PARSER_PROVIDER !== "llamaparse",
    "只有在 smoke 環境已啟用 llamaparse provider 時才執行。",
  );

  await loginViaPublicKeycloak(page);
  const areaName = `LlamaParse-Smoke-${Date.now()}`;
  await createAndOpenSmokeArea(page, { areaName, description: "LlamaParse smoke area" });
  await page.click('button:has-text("管理文件")');
  await page.setInputFiles('input[data-testid="document-upload"]', {
    name: `llamaparse-${Date.now()}.pdf`,
    mimeType: "application/pdf",
    buffer: MINIMAL_TEXT_PDF,
  });
  await page.click('button[data-testid="upload-document-submit"]');

  await expect(page.getByText("ready")).toBeVisible({ timeout: 60000 });
});
