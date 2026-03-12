/** React 前端骨架的應用程式啟動入口。 */

import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./app/App";
import "./styles.css";


ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
