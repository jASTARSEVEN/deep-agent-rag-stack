/** React 前端骨架的主 landing page。 */

import { useEffect, useState } from "react";

import { HealthPanel } from "../components/HealthPanel";
import { RoadmapPanel } from "../components/RoadmapPanel";
import { fetchApiHealth } from "../lib/api";
import { appConfig, plannedServices } from "../lib/config";
import type { ApiHealthState } from "../lib/types";


/** 渲染骨架 landing page，並顯示目前 API 健康狀態。 */
export function App(): JSX.Element {
  const [healthState, setHealthState] = useState<ApiHealthState>({
    status: "loading",
  });

  useEffect(() => {
    let isMounted = true;

    async function loadHealth(): Promise<void> {
      try {
        const response = await fetchApiHealth();
        if (!isMounted) {
          return;
        }
        setHealthState({
          status: "success",
          payload: response,
        });
      } catch (error) {
        if (!isMounted) {
          return;
        }
        const message = error instanceof Error ? error.message : "未知的 API health 錯誤";
        setHealthState({
          status: "error",
          message,
        });
      }
    }

    void loadHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#efe8da,_#d6dbc8_45%,_#c4cfbd_100%)] text-ink">
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-10">
        <header className="rounded-3xl border border-moss/20 bg-white/80 p-8 shadow-[0_24px_80px_rgba(18,33,23,0.08)] backdrop-blur">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-ember">MVP 骨架</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight">{appConfig.appName}</h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-ink/80">
            本輪只建立 API、worker、web 與本機基礎設施之間的可執行接線。
            Knowledge Area、documents、auth、chat 等正式業務邏輯刻意延後到後續階段。
          </p>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <HealthPanel apiBaseUrl={appConfig.apiBaseUrl} healthState={healthState} services={plannedServices} />
          <RoadmapPanel />
        </section>
      </div>
    </main>
  );
}
