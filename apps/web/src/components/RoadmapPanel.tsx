/** 說明本輪刻意範圍限制的 roadmap panel 元件。 */


// 本輪刻意維持在範圍外、留待後續階段實作的產品能力。
const deferredItems = [
  "Keycloak login 與 callback flow",
  "Knowledge Area CRUD 與 access management",
  "文件上傳流程與進度顯示",
  "Chat、citations、retrieval、SQL gate、FTS、rerank",
];


/** 渲染本輪 roadmap 與目前延後的功能清單。 */
export function RoadmapPanel(): JSX.Element {
  return (
    <section className="rounded-3xl border border-moss/20 bg-ink p-6 text-sand shadow-[0_18px_50px_rgba(18,33,23,0.18)]">
      <h2 className="text-xl font-semibold">目前骨架涵蓋範圍</h2>
      <ul className="mt-5 space-y-3 text-sm leading-6 text-sand/85">
        <li>FastAPI 提供 landing route 與 health route。</li>
        <li>Celery 提供最小 ping task 與健康檢查腳本。</li>
        <li>React 顯示服務接線狀態與 API health。</li>
        <li>Docker Compose 已把本機基礎設施與應用容器串起來。</li>
      </ul>
      <div className="mt-6 rounded-2xl bg-white/10 p-4">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-sand/70">延後到後續階段</p>
        <ul className="mt-3 space-y-2 text-sm text-sand/90">
          {deferredItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
