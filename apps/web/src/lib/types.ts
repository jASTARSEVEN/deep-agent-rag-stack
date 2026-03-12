/** React 前端骨架 UI 使用的共用型別。 */


/** landing page 上顯示的服務中繼資料。 */
export interface PlannedService {
  name: string;
  kind: string;
  description: string;
}


/** FastAPI 骨架服務回傳的 API health payload。 */
export interface ApiHealthPayload {
  status: string;
  service: string;
  version: string;
}


/** API health 請求生命週期使用的本機元件狀態。 */
export type ApiHealthState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; payload: ApiHealthPayload };
