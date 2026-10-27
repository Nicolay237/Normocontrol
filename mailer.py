# -*- coding: utf-8 -*-
"""
Служебные письма (код подтверждения почты, сброс пароля) через SMTP почтового сервиса.

Напрямую с VPS письма не отправляем: у IP сервера нет почтовой репутации, письма уйдут в спам,
а порт 25 хостинг закрывает. Почтовый сервис (почта рег.ру на домене) отправляет от своего имени.

  SMTP_HOST      mail.hosting.reg.ru
  SMTP_PORT      465 (SSL) или 587 (STARTTLS)
  SMTP_USER      noreply@normocontrol.site — полный адрес ящика
  SMTP_PASSWORD  пароль от ящика
  MAIL_FROM      адрес отправителя (по умолчанию SMTP_USER)

Пока SMTP не настроен, enabled() — False: регистрация работает без подтверждения почты.
Для разработки: SMTP_HOST=console — письма не отправляются, а печатаются в журнал сервера.
"""

import os
import ssl
import smtplib
import logging
import threading
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

log = logging.getLogger("normocontrol.mail")


def _cfg():
    env = lambda k, d="": os.environ.get(k, d).strip()
    user = env("SMTP_USER")
    return {"host": env("SMTP_HOST"), "port": int(env("SMTP_PORT", "465") or 465), "user": user,
            "password": env("SMTP_PASSWORD"), "from": env("MAIL_FROM") or user}


def enabled():
    c = _cfg()
    return c["host"] == "console" or bool(c["host"] and c["user"] and c["password"])


def send(to, subject, text):
    """Отправляет письмо. Ошибку SMTP пробрасывает — вызывающий решает, что сказать пользователю."""
    c = _cfg()
    if c["host"] == "console":
        log.warning("письмо для %s: %s\n%s", to, subject, text)
        return
    msg = EmailMessage()
    msg["From"] = formataddr(("Нормоконтроль", c["from"]))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=c["from"].split("@")[-1])
    msg.set_content(text)
    ctx = ssl.create_default_context()
    if c["port"] == 465:
        with smtplib.SMTP_SSL(c["host"], c["port"], context=ctx, timeout=20) as s:
            s.login(c["user"], c["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(c["host"], c["port"], timeout=20) as s:
            s.starttls(context=ctx)
            s.login(c["user"], c["password"])
            s.send_message(msg)
    log.info("письмо «%s» отправлено", subject)


def code_letter(kind, code, site):
    """Текст письма с кодом: kind — verify (подтверждение почты) или reset (сброс пароля)."""
    if kind == "verify":
        subject = f"Код подтверждения: {code}"
        intro = "Вы зарегистрировались на сайте «Нормоконтроль». Чтобы подтвердить почту, введите код:"
    else:
        subject = f"Сброс пароля: код {code}"
        intro = "Кто-то (возможно, вы) запросил сброс пароля на сайте «Нормоконтроль». Код для сброса:"
    text = (f"Здравствуйте!\n\n{intro}\n\n    {code}\n\nКод действует 30 минут.\n\n"
            f"Если вы ничего не запрашивали, просто проигнорируйте это письмо.\n\n"
            f"— Нормоконтроль, {site}\n")
    return subject, text


# ── письма администратору о сбоях ─────────────────────────────────────────

class AlertHandler(logging.Handler):
    """Ошибки из журнала — письмом на ALERT_EMAIL (или CONTACT_EMAIL).

    Одинаковые ошибки не чаще раза в REPEAT секунд, всего не больше DAILY писем в сутки:
    при массовом сбое почта не должна превратиться в спам. Отправка — в отдельном потоке,
    чтобы пользователь не ждал SMTP."""

    REPEAT, DAILY = 30 * 60, 30

    def __init__(self, to):
        super().__init__(logging.ERROR)
        self.to = to
        self._sent = {}          # первая строка ошибки → когда отправляли
        self._day = (None, 0)    # (дата, сколько писем за неё)
        self._lock = threading.Lock()

    def _allow(self, key, now):
        with self._lock:
            day = time.strftime("%Y-%m-%d", time.localtime(now))
            count = self._day[1] if self._day[0] == day else 0
            if count >= self.DAILY or now - self._sent.get(key, 0) < self.REPEAT:
                return False
            self._sent[key] = now
            self._day = (day, count + 1)
            return True

    def emit(self, record):
        try:
            text = self.format(record)
            if not self._allow(f"{record.name}:{record.getMessage()[:200]}", record.created):
                return
            subject = f"Сбой на сайте: {record.getMessage()[:80]}"
            threading.Thread(target=self._send, args=(subject, text), daemon=True).start()
        except Exception:
            self.handleError(record)

    def _send(self, subject, text):
        try:
            send(self.to, subject, text)
        except Exception as e:  # письмо о сбое не должно рождать новый сбой
            log.warning("письмо о сбое не отправлено: %s", e)


def install_alerts(*loggers):
    """Подключает AlertHandler к журналам, если почта настроена и есть кому писать."""
    to = os.environ.get("ALERT_EMAIL", "").strip() or os.environ.get("CONTACT_EMAIL", "").strip()
    if not (to and enabled()):
        return None
    handler = AlertHandler(to)
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s\n%(message)s"))
    for lg in loggers:
        lg.addHandler(handler)
    return handler
