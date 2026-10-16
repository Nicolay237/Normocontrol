import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

// Material Web (официальные компоненты Material 3)
import "@material/web/button/filled-button.js";
import "@material/web/button/filled-tonal-button.js";
import "@material/web/button/outlined-button.js";
import "@material/web/button/text-button.js";
import "@material/web/icon/icon.js";
import "@material/web/iconbutton/icon-button.js";
import "@material/web/progress/linear-progress.js";
import "@material/web/progress/circular-progress.js";
import "@material/web/ripple/ripple.js";
import "@material/web/divider/divider.js";
import "@material/web/list/list.js";
import "@material/web/list/list-item.js";

import App from "./App.jsx";
import "./theme.css";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
