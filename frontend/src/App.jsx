import { NavLink, Link, Route, Routes, useLocation } from "react-router-dom";
import { ProfilesProvider, useSession } from "./ProfilesContext.jsx";
import { Icon, Logo } from "./ui.jsx";
import Home from "./pages/Home.jsx";
import CheckPage from "./pages/CheckPage.jsx";
import Login from "./pages/Login.jsx";
import Account from "./pages/Account.jsx";
import Admin from "./pages/Admin.jsx";
import Gost from "./pages/Gost.jsx";
import StandardsPage from "./pages/StandardsPage.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";

function UserButton() {
  const { user } = useSession();
  const location = useLocation();
  if (!user)
    return (
      <Link to="/login" state={{ from: location.pathname }} className="account-btn label-large" aria-label="Войти">
        <Icon name="login" size={20} /><span className="account-text">Войти</span>
        <md-ripple />
      </Link>
    );
  return (
    <Link to={user.role === "admin" ? "/admin" : "/account"} className="account-btn label-large"
          aria-label={`Аккаунт: ${user.name}`} title={user.name}>
      <Icon name={user.role === "admin" ? "admin" : "user"} size={20} />
      <span className="account-text">{user.name.split(" ")[0]}</span>
      <md-ripple />
    </Link>
  );
}

export default function App() {
  return (
    <ProfilesProvider>
      <header className="app-bar">
        <div className="container app-bar-inner">
          <Link to="/" className="brand title-large">
            <Logo />
            <span className="brand-text">Нормоконтроль</span>
          </Link>
          <nav className="tabs" aria-label="Тип работы">
            <NavLink to="/vkr" className="tab label-large">ВКР<md-ripple /></NavLink>
            <NavLink to="/coursework" className="tab label-large">Курсовая<md-ripple /></NavLink>
            <NavLink to="/standards" className="tab label-large">ГОСТы<md-ripple /></NavLink>
          </nav>
          <span className="gost label-medium">ГОСТ 7.32&#8209;2017</span>
          <ThemeToggle />
          <UserButton />
        </div>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/vkr" element={<CheckPage profileKey="vkr" />} />
          <Route path="/coursework" element={<CheckPage profileKey="coursework" />} />
          <Route path="/gost" element={<Gost />} />
          <Route path="/standards" element={<StandardsPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Login mode="register" />} />
          <Route path="/account" element={<Account />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Home notFound />} />
        </Routes>
      </main>

      <footer className="container">
        <div className="app-footer body-medium">
          <nav className="footer-links label-large" aria-label="Разделы сайта">
            <Link to="/vkr">Проверка ВКР</Link>
            <Link to="/coursework">Проверка курсовой</Link>
            <Link to="/standards">Проверка по выбранным ГОСТам</Link>
            <Link to="/gost">Требования ГОСТ 7.32-2017</Link>
          </nav>
          <p>
            Нормы приведены по ГОСТ 7.32&#8209;2017. Сервис даёт предварительную оценку —
            окончательное решение остаётся за нормоконтролем вашей кафедры.
          </p>
        </div>
      </footer>
    </ProfilesProvider>
  );
}
