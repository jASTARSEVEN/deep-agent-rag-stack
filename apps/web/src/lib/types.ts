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


/** 已驗證使用者的最小 auth context。 */
export interface AuthContextPayload {
  sub: string;
  groups: string[];
  authenticated: boolean;
}


/** 前端 auth provider 對外暴露的 session 狀態。 */
export interface AuthSessionState {
  isLoading: boolean;
  isAuthenticated: boolean;
  accessToken: string | null;
  principal: AuthContextPayload | null;
}


/** Area 角色型別。 */
export type AreaRole = "reader" | "maintainer" | "admin";


/** Area list 與 detail 共用的 API 型別。 */
export interface AreaSummary {
  id: string;
  name: string;
  description: string | null;
  effective_role: AreaRole;
  created_at: string;
  updated_at: string;
}


/** Area list API payload。 */
export interface AreaListPayload {
  items: AreaSummary[];
}


/** 單一 user access entry。 */
export interface AccessUserEntry {
  user_sub: string;
  role: AreaRole;
}


/** 單一 group access entry。 */
export interface AccessGroupEntry {
  group_path: string;
  role: AreaRole;
}


/** Area access management payload。 */
export interface AreaAccessPayload {
  area_id: string;
  users: AccessUserEntry[];
  groups: AccessGroupEntry[];
}


/** API health 請求生命週期使用的本機元件狀態。 */
export type ApiHealthState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; payload: ApiHealthPayload };
