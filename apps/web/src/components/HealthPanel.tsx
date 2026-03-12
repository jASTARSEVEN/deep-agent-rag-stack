/** 用來顯示目前 stack 接線狀態的 health panel 元件。 */

import type { ApiHealthState, PlannedService } from "../lib/types";


/** 渲染前端視角下的後端接線與服務可用性。 */
export function HealthPanel(props: {
  apiBaseUrl: string;
  healthState: ApiHealthState;
  services: PlannedService[];
}): JSX.Element {
  const { apiBaseUrl, healthState, services } = props;

  return (
    <section className="rounded-3xl border border-moss/20 bg-white/85 p-6 shadow-[0_18px_50px_rgba(18,33,23,0.08)]">
      <h2 className="text-xl font-semibold">Stack 接線狀態</h2>
      <p className="mt-2 text-sm text-ink/70">前端 API 目標：{apiBaseUrl}</p>
      <div className="mt-5 rounded-2xl bg-sand/70 p-4">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-moss">API 健康狀態</p>
        {healthState.status === "loading" ? <p className="mt-2 text-sm">正在檢查 API health...</p> : null}
        {healthState.status === "error" ? (
          <p className="mt-2 text-sm text-ember">API health 檢查失敗：{healthState.message}</p>
        ) : null}
        {healthState.status === "success" ? (
          <div className="mt-3 space-y-2 text-sm">
            <p>狀態：{healthState.payload.status}</p>
            <p>服務：{healthState.payload.service}</p>
            <p>版本：{healthState.payload.version}</p>
          </div>
        ) : null}
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {services.map((service) => (
          <article key={service.name} className="rounded-2xl border border-moss/15 bg-white p-4">
            <p className="text-sm font-semibold">{service.name}</p>
            <p className="mt-1 text-xs uppercase tracking-[0.16em] text-moss">{service.kind}</p>
            <p className="mt-3 text-sm text-ink/70">{service.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
