import { NavLink, Link, Route, Routes } from "react-router-dom";
import { ProfilesProvider } from "./ProfilesContext.jsx";
import Home from "./pages/Home.jsx";
import CheckPage from "./pages/CheckPage.jsx";

export default function App() {
  return (
    <ProfilesProvider>
      <nav className="nav">
        <Link to="/" className="nav-mark">
          <span className="nav-seal">⬤</span> Нормоконтроль
        </Link>
        <div className="nav-links">
          <NavLink to="/vkr">ВКР</NavLink>
          <NavLink to="/coursework">Курсовая</NavLink>
          <span className="nav-std">ГОСТ 7.32&#8209;2017</span>
        </div>
      </nav>

      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/vkr" element={<CheckPage profileKey="vkr" />} />
          <Route path="/coursework" element={<CheckPage profileKey="coursework" />} />
          <Route path="*" element={<Home notFound />} />
        </Routes>
      </main>

      <footer className="site-footer">
        <p>
          Нормы приведены по ГОСТ 7.32&#8209;2017. Сервис даёт предварительную оценку —
          окончательное решение остаётся за нормоконтролем вашей кафедры.
        </p>
      </footer>
    </ProfilesProvider>
  );
}
