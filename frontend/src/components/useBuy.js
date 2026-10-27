import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { createOrder } from "../api.js";
import { useProfiles } from "../ProfilesContext.jsx";
import { goal } from "../metrika.js";

/**
 * Покупка: разовое исправление (kind = "autofix") или подписка ("subscription").
 * Без аккаунта — на регистрацию (потом вернём на эту же страницу), без подтверждённой почты —
 * на ввод кода; иначе создаём заказ и уходим на страницу оплаты ЮKassa.
 */
export default function useBuy() {
  const { config } = useProfiles();
  const navigate = useNavigate();
  const location = useLocation();
  const [state, setState] = useState({ busy: null, error: null, soon: false });

  async function buy(kind, extra = {}) {
    goal("buy_click", { kind });   // намерение купить — ещё до регистрации и оплаты
    const user = config.user;
    if (!config.payments_enabled) return setState({ busy: null, error: null, soon: true });
    if (!user) return navigate("/register", { state: { from: location.pathname } });
    if (user.email_verified === false) return navigate("/verify", { state: { from: location.pathname } });
    setState({ busy: kind, error: null, soon: false });
    try {
      const res = await createOrder({ kind, ...extra });
      window.location.assign(res.confirmation_url);
    } catch (e) {
      if (e.code === "email_unverified") return navigate("/verify", { state: { from: location.pathname } });
      setState({ busy: null, error: e.message, soon: false });
    }
    return undefined;
  }

  return { buy, ...state };
}
