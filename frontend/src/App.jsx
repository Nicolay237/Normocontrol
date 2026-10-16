import { NavLink, Link, Route, Routes } from "react-router-dom";
import { ProfilesProvider } from "./ProfilesContext.jsx";
import { Icon } from "./ui.jsx";
import Home from "./pages/Home.jsx";
import CheckPage from "./pages/CheckPage.jsx";

export default function App() {
  return (
    <ProfilesProvider>
      <header className="app-bar">
        <Link to="/" className="brand title-large">
          <span className="brand-mark"><Icon name="brand" /></span>
          Нормоконтроль
        </Link>
        <nav className="tabs" aria-label="Тип работы">
          <NavLink to="/vkr" className="tab label-large">ВКР<md-ripple /></NavLink>
          <NavLink to="/coursework" className="tab label-large">Курсовая<md-ripple /></NavLink>
        </nav>
        <span className="gost label-medium">ГОСТ 7.32&#8209;2017</span>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/vkr" element={<CheckPage profileKey="vkr" />} />
          <Route path="/coursework" element={<CheckPage profileKey="coursework" />} />
          <Route path="*" element={<Home notFound />} />
        </Routes>
      </main>

      <footer className="app-footer body-medium">
        Нормы приведены по ГОСТ 7.32&#8209;2017. Сервис даёт предварительную оценку —
        окончательное решение остаётся за нормоконтролем вашей кафедры.
      </footer>
    </ProfilesProvider>
  );
}
