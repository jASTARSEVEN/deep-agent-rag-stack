/** Compose smoke 測試 local PDF upload 流程，入口固定走 Caddy。 */

import { expect, test } from "@playwright/test";

import { createAndOpenSmokeArea, loginViaPublicKeycloak } from "../support/publicEntry";


/** 可被 local PDF parser 擷取文字的最小 PDF 測試樣本。 */
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
(Deep Agent PDF local parser sample) Tj
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


test("應可在 compose smoke 中完成 PDF 上傳並看到 ready", async ({ page }) => {
  await loginViaPublicKeycloak(page);

  const areaName = `PDF-Smoke-${Date.now()}`;
  await createAndOpenSmokeArea(page, { areaName, description: "PDF smoke area" });

  await page.click('button:has-text("管理文件")');
  const fileName = `smoke-${Date.now()}.pdf`;
  await page.setInputFiles('input[data-testid="document-upload"]', {
    name: fileName,
    mimeType: "application/pdf",
    buffer: MINIMAL_TEXT_PDF,
  });
  await page.click('button[data-testid="upload-document-submit"]');

  const documentCard = page.getByTestId("documents-list").locator("article").filter({ hasText: fileName });
  await expect(documentCard).toContainText("ready", { timeout: 60000 });
});
